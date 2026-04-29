from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest
from fastapi.responses import PlainTextResponse
from functools import lru_cache
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError
import time, logging
from rag import get_rag_chain
from sentiment import analyze_sentiment

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SupportMind API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics
REQUEST_COUNT = Counter("supportmind_requests_total", "Total requests", ["endpoint"])
LATENCY = Histogram("supportmind_latency_seconds", "Request latency", ["endpoint"])
SENTIMENT_DIST = Counter("supportmind_sentiment_total", "Sentiment counts", ["sentiment"])
CACHE_HITS = Counter("supportmind_cache_hits_total", "Total cache hits")
CACHE_MISSES = Counter("supportmind_cache_misses_total", "Total cache misses")
RETRY_COUNT = Counter("supportmind_retries_total", "Total retry attempts", ["endpoint"])
CIRCUIT_OPEN = Counter("supportmind_circuit_open_total", "Times circuit breaker opened", ["endpoint"])

# Load RAG chain once on startup
rag_chain, retriever = get_rag_chain()

# Circuit breaker state
_failure_count = 0
_circuit_open = False
_circuit_opened_at = 0.0
FAILURE_THRESHOLD = 5      # open circuit after 5 consecutive failures
RECOVERY_TIMEOUT = 30.0    # try again after 30 seconds


class ChatRequest(BaseModel):
    message: str
    conversation_id: str = "default"


class SentimentRequest(BaseModel):
    message: str


def normalize_query(message: str) -> str:
    return message.strip().lower()


def check_circuit():
    """Raise 503 immediately if circuit is open and recovery window hasn't passed."""
    global _circuit_open, _failure_count, _circuit_opened_at
    if _circuit_open:
        elapsed = time.time() - _circuit_opened_at
        if elapsed < RECOVERY_TIMEOUT:
            raise HTTPException(
                status_code=503,
                detail=f"Service temporarily unavailable (circuit open, retry in {int(RECOVERY_TIMEOUT - elapsed)}s)"
            )
        else:
            # Half-open: allow one attempt through
            logger.info("Circuit breaker half-open — attempting recovery")
            _circuit_open = False
            _failure_count = 0


def record_success():
    global _failure_count, _circuit_open
    _failure_count = 0
    _circuit_open = False


def record_failure(endpoint: str):
    global _failure_count, _circuit_open, _circuit_opened_at
    _failure_count += 1
    if _failure_count >= FAILURE_THRESHOLD:
        _circuit_open = True
        _circuit_opened_at = time.time()
        CIRCUIT_OPEN.labels(endpoint=endpoint).inc()
        logger.warning(f"Circuit breaker OPENED after {_failure_count} failures on {endpoint}")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    reraise=True
)
def _rag_with_retry(message: str):
    """Call RAG chain with automatic retry on transient failures (3 attempts, exponential backoff)."""
    return rag_chain.invoke({"query": message})


@lru_cache(maxsize=100)
def cached_rag(normalized_message: str):
    """LRU-cached RAG call. Cache key is the normalized query string."""
    result = _rag_with_retry(normalized_message)
    return {
        "answer": result["result"],
        "sources": [
            {
                "content": doc.page_content[:200],
                "source": doc.metadata.get("source", "unknown")
            }
            for doc in result.get("source_documents", [])
        ]
    }


@app.post("/chat")
async def chat(req: ChatRequest):
    REQUEST_COUNT.labels(endpoint="chat").inc()
    start = time.time()

    # Circuit breaker check — fail fast if downstream is unhealthy
    check_circuit()

    try:
        query = normalize_query(req.message)

        before = cached_rag.cache_info().hits
        result = cached_rag(query)
        after = cached_rag.cache_info().hits

        cache_status = "hit" if after > before else "miss"

        if cache_status == "hit":
            CACHE_HITS.inc()
        else:
            CACHE_MISSES.inc()

        record_success()
        LATENCY.labels(endpoint="chat").observe(time.time() - start)
        logger.info(f"Chat completed in {time.time()-start:.3f}s | cache={cache_status}")

        return {
            "answer": result["answer"],
            "sources": result["sources"],
            "latency_ms": round((time.time() - start) * 1000, 2),
            "cache": cache_status
        }

    except RetryError as e:
        # All 3 retry attempts exhausted
        RETRY_COUNT.labels(endpoint="chat").inc()
        record_failure("chat")
        logger.error(f"All retries exhausted for /chat: {e}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable after retries")

    except HTTPException:
        raise  # Re-raise circuit-breaker 503s as-is

    except Exception as e:
        record_failure("chat")
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")


@app.post("/sentiment")
async def sentiment(req: SentimentRequest):
    REQUEST_COUNT.labels(endpoint="sentiment").inc()
    start = time.time()

    result = analyze_sentiment(req.message)
    SENTIMENT_DIST.labels(sentiment=result["sentiment"]).inc()
    LATENCY.labels(endpoint="sentiment").observe(time.time() - start)

    return result


@app.get("/metrics")
async def metrics():
    return PlainTextResponse(generate_latest())


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "circuit_open": _circuit_open,
        "failure_count": _failure_count
    }


@app.get("/cache")
async def cache_info():
    info = cached_rag.cache_info()
    return {
        "hits": info.hits,
        "misses": info.misses,
        "maxsize": info.maxsize,
        "currsize": info.currsize,
        "hit_rate": round(info.hits / max(info.hits + info.misses, 1) * 100, 1)
    }
