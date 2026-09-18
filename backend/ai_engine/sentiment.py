import gc, torch
from transformers import pipeline

class FinBERTSentiment:
    def __init__(self): self.pipe = None; self.device = 0 if torch.cuda.is_available() else -1
    def _load(self):
        if self.pipe is None:
            self.pipe = pipeline("sentiment-analysis", model="ProsusAI/finbert", tokenizer="ProsusAI/finbert", device=self.device, truncation=True, max_length=256)
    def analyze(self, text):
        self._load(); result = self.pipe(text[:2000])[0]; label = result["label"].lower(); probability = float(result["score"])
        score = probability if label == "positive" else -probability if label == "negative" else 0.0
        return {"sentiment": label, "score": round(score, 4), "confidence": round(probability, 4)}
    def unload(self):
        self.pipe = None; gc.collect()
        if torch.cuda.is_available(): torch.cuda.empty_cache()
