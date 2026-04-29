from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest
from fastapi.responses import PlainTextResponse
from functools import lru_cache
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

REQUEST_COUNT = Counter("supportmind_requests_total", "Total requests", ["endpoint"])
LATENCY = Histogram("supportmind_latency_seconds", "Request latency", ["endpoint"])
SENTIMENT_DIST = Counter("supportmind_sentiment_total", "Sentiment counts", ["sentiment"])
CACHE_HITS = Counter("supportmind_cache_hits_total", "Total cache hits")
CACHE_MISSES = Counter("supportmind_cache_misses_total", "Total cache misses")

rag_chain, retriever = get_rag_chain()

class ChatRequest(BaseModel):
    message: str
    conversation_id: str = "default"

class SentimentRequest(BaseModel):
    message: str

def normalize_query(message: str) -> str:
    return message.strip().lower()

@lru_cache(maxsize=100)
def cached_rag(normalized_message: str):
    result = rag_chain.invoke({"query": normalized_message})
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

        LATENCY.labels(endpoint="chat").observe(time.time() - start)
        logger.info(f"Chat completed in {time.time()-start:.3f}s, cache={cache_status}")

        return {
            "answer": result["answer"],
            "sources": result["sources"],
            "latency_ms": round((time.time() - start) * 1000, 2),
            "cache": cache_status
        }

    except Exception as e:
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
    return {"status": "ok"}

@app.get("/cache")
async def cache_info():
    return {
        "cache_info": str(cached_rag.cache_info())
    }