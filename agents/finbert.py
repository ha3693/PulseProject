"""Hugging Face FinBERT financial domain sentiment scoring engine for Pulse.
Provides fast, deterministic financial NLP inference using ProsusAI/finbert.
Outputs calibrated sentiment scores (-100 to +100), label classifications,
and softmax confidence distributions.
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("PulseFinBERT")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

FINBERT_MODEL_NAME = "ProsusAI/finbert"


class FinBERTScorer:
    """Singleton inference wrapper for Hugging Face ProsusAI/finbert."""

    _instance: Optional["FinBERTScorer"] = None

    def __init__(self, model_name: str = FINBERT_MODEL_NAME, device: Optional[str] = None):
        self.model_name = model_name
        self.tokenizer = None
        self.model = None
        self.device = device
        self.is_loaded = False
        self._load_model()

    @classmethod
    def get_instance(cls) -> "FinBERTScorer":
        """Get or initialize the shared FinBERTScorer singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_model(self):
        """Load tokenizer and model weights onto the target device."""
        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForSequenceClassification

            # Auto-detect Apple Silicon MPS or fallback to CPU
            if not self.device:
                if torch.backends.mps.is_available():
                    self.device = "mps"
                elif torch.cuda.is_available():
                    self.device = "cuda"
                else:
                    self.device = "cpu"

            logger.info(f"Loading Hugging Face model '{self.model_name}' on device '{self.device}'...")
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
            self.model.to(self.device)
            self.model.eval()
            self.is_loaded = True
            logger.info("FinBERT model successfully loaded and ready for signal scoring.")

        except Exception as e:
            logger.warning(f"Could not load local FinBERT model ({e}). Will run in heuristic fallback mode.")
            self.is_loaded = False

    def score_text(self, text: str) -> Dict[str, Any]:
        """
        Score a single piece of text using FinBERT.

        Returns:
            Dict containing:
                - label: 'positive', 'neutral', or 'negative'
                - score: float between -100.0 (bearish) and +100.0 (bullish)
                - confidence: float between 0.0 and 1.0 (softmax probability)
                - probabilities: Dict[str, float] with 'positive', 'neutral', 'negative'
        """
        if not self.is_loaded or not text or not text.strip():
            return {
                "label": "neutral",
                "score": 0.0,
                "confidence": 0.5,
                "probabilities": {"positive": 0.33, "neutral": 0.34, "negative": 0.33},
            }

        import torch

        # Truncate text cleanly to prevent tensor overflow
        clean_text = text.strip()[:1000]

        inputs = self.tokenizer(
            clean_text,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt"
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)
            probs = torch.nn.functional.softmax(outputs.logits, dim=-1)[0]

        # ProsusAI/finbert class indices: 0 -> positive, 1 -> negative, 2 -> neutral
        pos_prob = float(probs[0].item())
        neg_prob = float(probs[1].item())
        neu_prob = float(probs[2].item())

        labels = ["positive", "negative", "neutral"]
        max_idx = int(torch.argmax(probs).item())
        predicted_label = labels[max_idx]
        confidence = float(probs[max_idx].item())

        # Net sentiment calibrated in [-100.0, +100.0]
        net_score = round((pos_prob - neg_prob) * 100.0, 2)

        return {
            "label": predicted_label,
            "score": net_score,
            "confidence": round(confidence, 4),
            "probabilities": {
                "positive": round(pos_prob, 4),
                "negative": round(neg_prob, 4),
                "neutral": round(neu_prob, 4),
            },
        }

    def score_posts(self, posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Batch score a list of posts or articles using FinBERT.
        Mutates and enriches each post dict with finbert_* keys.
        """
        if not posts:
            return []

        if not self.is_loaded:
            logger.warning("FinBERT not loaded. Skipping deep sequence classification.")
            return posts

        import torch

        texts = []
        for p in posts:
            # Combine title and snippet/content text for comprehensive financial context
            title = p.get("title", "")
            content = p.get("content_text", "")
            full_text = f"{title}. {content}".strip() if title != content else title
            texts.append(full_text[:512] if full_text else "Market update.")

        inputs = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt"
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)
            probs = torch.nn.functional.softmax(outputs.logits, dim=-1)

        labels = ["positive", "negative", "neutral"]

        for i, p in enumerate(posts):
            row = probs[i]
            pos_prob = float(row[0].item())
            neg_prob = float(row[1].item())
            neu_prob = float(row[2].item())

            max_idx = int(torch.argmax(row).item())
            pred_label = labels[max_idx]
            confidence = float(row[max_idx].item())
            net_score = round((pos_prob - neg_prob) * 100.0, 2)

            p["finbert_label"] = pred_label
            p["finbert_score"] = net_score
            p["finbert_confidence"] = round(confidence, 4)
            p["finbert_probabilities"] = {
                "positive": round(pos_prob, 4),
                "negative": round(neg_prob, 4),
                "neutral": round(neu_prob, 4),
            }

        return posts

    def compute_aggregate(self, posts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compute overall aggregate FinBERT sentiment metrics across a list of scored posts.
        """
        if not posts:
            return {
                "aggregate_score": 0.0,
                "breakdown": {"positive": 0, "neutral": 0, "negative": 0},
            }

        pos_count = 0
        neg_count = 0
        neu_count = 0
        total_score = 0.0

        for p in posts:
            label = p.get("finbert_label")
            score = p.get("finbert_score", 0.0)

            if label == "positive":
                pos_count += 1
            elif label == "negative":
                neg_count += 1
            else:
                neu_count += 1

            total_score += score

        avg_score = round(total_score / max(len(posts), 1), 1)

        return {
            "aggregate_score": avg_score,
            "breakdown": {
                "positive": pos_count,
                "neutral": neu_count,
                "negative": neg_count,
            },
        }


def get_finbert_scorer() -> FinBERTScorer:
    """Helper to retrieve the global FinBERT scorer instance."""
    return FinBERTScorer.get_instance()


if __name__ == "__main__":
    import sys

    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Apple reports quarterly earnings beat and expands $110B stock buyback."
    scorer = get_finbert_scorer()
    res = scorer.score_text(query)

    print("\n" + "=" * 65)
    print("📈 HUGGING FACE FINBERT SENTIMENT ANALYSIS")
    print("=" * 65)
    print(f"Text:       {query}")
    print(f"Sentiment:  {res['label'].upper()} (Confidence: {res['confidence'] * 100:.1f}%)")
    print(f"Net Score:  {res['score']:+.2f} (-100.0 to +100.0)")
    print(f"Softmax:    Positive: {res['probabilities']['positive']:.3f} | Neutral: {res['probabilities']['neutral']:.3f} | Negative: {res['probabilities']['negative']:.3f}")
    print("=" * 65 + "\n")
