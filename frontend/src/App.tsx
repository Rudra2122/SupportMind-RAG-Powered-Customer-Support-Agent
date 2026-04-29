import { useState } from "react";
import axios from "axios";

const API = "http://localhost:8000";

type Sentiment = "positive" | "neutral" | "frustrated";

interface Source {
  content: string;
  source: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  sentiment?: Sentiment;
  sources?: Source[];
}

const sentimentColors: Record<Sentiment, string> = {
  positive: "#22c55e",
  neutral: "#94a3b8",
  frustrated: "#ef4444",
};

const sentimentEmoji: Record<Sentiment, string> = {
  positive: "😊",
  neutral: "😐",
  frustrated: "😤",
};

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function sendMessage() {
    if (!input.trim() || loading) return;
    const userMsg = input.trim();
    setInput("");
    setLoading(true);

    // Add user message + run sentiment in parallel
    const [_, sentimentRes] = await Promise.all([
      Promise.resolve(),
      axios.post(`${API}/sentiment`, { message: userMsg }),
    ]);

    const sentiment = sentimentRes.data.sentiment as Sentiment;

    setMessages((prev) => [
      ...prev,
      { role: "user", content: userMsg, sentiment },
    ]);

    try {
      const chatRes = await axios.post(`${API}/chat`, { message: userMsg });
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: chatRes.data.answer,
          sources: chatRes.data.sources,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Sorry, something went wrong. Please try again." },
      ]);
    }
    setLoading(false);
  }

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: "24px 16px", fontFamily: "system-ui, sans-serif" }}>
      <h1 style={{ fontSize: 22, fontWeight: 600, marginBottom: 4 }}>SupportMind</h1>
      <p style={{ color: "#64748b", fontSize: 14, marginBottom: 24 }}>
        RAG-powered customer support agent · Sentiment analysis
      </p>

      {/* Chat window */}
      <div style={{ border: "1px solid #e2e8f0", borderRadius: 12, padding: 16, minHeight: 400, marginBottom: 16, background: "#f8fafc" }}>
        {messages.length === 0 && (
          <p style={{ color: "#94a3b8", textAlign: "center", marginTop: 80 }}>
            Ask a support question to get started
          </p>
        )}
        {messages.map((msg, i) => (
          <div key={i} style={{ marginBottom: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: msg.role === "user" ? "#3b82f6" : "#7c3aed" }}>
                {msg.role === "user" ? "You" : "SupportMind"}
              </span>
              {/* Sentiment badge — only on user messages */}
              {msg.sentiment && (
                <span style={{
                  fontSize: 11,
                  padding: "2px 8px",
                  borderRadius: 99,
                  background: sentimentColors[msg.sentiment] + "22",
                  color: sentimentColors[msg.sentiment],
                  fontWeight: 600,
                  border: `1px solid ${sentimentColors[msg.sentiment]}44`
                }}>
                  {sentimentEmoji[msg.sentiment]} {msg.sentiment}
                </span>
              )}
            </div>

            <div style={{
              background: msg.role === "user" ? "#eff6ff" : "#ffffff",
              border: "1px solid #e2e8f0",
              borderRadius: 8,
              padding: "10px 14px",
              fontSize: 15,
              lineHeight: 1.6,
            }}>
              {msg.content}
            </div>

            {Source citations — responsible AI transparency }
            {{msg.sources && msg.sources.length > 0 && (
              <div style={{ marginTop: 8 }}>
                <p style={{ fontSize: 11, color: "#94a3b8", marginBottom: 4 }}>Sources used:</p>
                {msg.sources.map((s, j) => (
                  <div key={j} style={{
                    fontSize: 12,
                    background: "#f1f5f9",
                    border: "1px solid #e2e8f0",
                    borderRadius: 6,
                    padding: "6px 10px",
                    marginBottom: 4,
                    color: "#475569"
                  }}>
                    <span style={{ fontWeight: 600, color: "#7c3aed" }}>{s.source}</span> — {s.content}
                  </div>
                ))}
              </div>
            )} }
          </div>
        ))}
        {loading && (
          <div style={{ color: "#94a3b8", fontSize: 14 }}>SupportMind is thinking...</div>
        )}
      </div>

      {/* Input */}
      <div style={{ display: "flex", gap: 8 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendMessage()}
          placeholder="Type your support question..."
          style={{
            flex: 1, padding: "10px 14px", borderRadius: 8,
            border: "1px solid #e2e8f0", fontSize: 15, outline: "none"
          }}
        />
        <button
          onClick={sendMessage}
          disabled={loading}
          style={{
            padding: "10px 20px", borderRadius: 8, border: "none",
            background: "#7c3aed", color: "#fff", fontWeight: 600,
            cursor: loading ? "not-allowed" : "pointer", opacity: loading ? 0.6 : 1
          }}
        >
          Send
        </button>
      </div>
    </div>
  );
}
