from transformers import pipeline

# Load once (fast after first run)
classifier = pipeline(
    "sentiment-analysis",
    model="distilbert-base-uncased-finetuned-sst-2-english"
)

def analyze_sentiment(text: str) -> dict:
    result = classifier(text)[0]

    label = result["label"]
    score = float(result["score"])

    # Map to your categories
    if label == "NEGATIVE":
        sentiment = "frustrated"
        urgency = "high"
    elif label == "POSITIVE":
        sentiment = "positive"
        urgency = "low"
    else:
        sentiment = "neutral"
        urgency = "medium"

    return {
        "sentiment": sentiment,
        "confidence": round(score, 2),
        "urgency": urgency
    }