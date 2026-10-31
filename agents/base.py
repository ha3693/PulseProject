"""Base agent class and shared utilities for Pulse intelligence agents."""

import os
import sys
import json
import uuid
import logging
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

logger = logging.getLogger("PulseBaseAgent")


def load_env():
    """Load environment variables from project root .env or parent directories."""
    try:
        from dotenv import load_dotenv
        project_root = Path(__file__).resolve().parent.parent
        for p in [project_root / ".env", Path(".env")]:
            if p.exists():
                load_dotenv(p)
                return
    except ImportError:
        pass

    # Standard library fallback
    project_root = Path(__file__).resolve().parent.parent
    for p in [project_root / ".env", Path(".env")]:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip('"').strip("'")
                            if k not in os.environ:
                                os.environ[k] = v
            except Exception:
                pass


load_env()


def get_llm():
    """
    Instantiate preferred Chat model based on environment keys with graceful fallback.
    Priority: OpenAI -> Google Gemini -> Anthropic Claude -> None (heuristic mode).
    """
    # 1. OpenAI (Default in user environment)
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key and not openai_key.startswith("your-"):
        try:
            from langchain_openai import ChatOpenAI
            logger.info("Using OpenAI (gpt-4o-mini) for agent reasoning.")
            return ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.2,
                api_key=openai_key
            )
        except Exception as e:
            logger.warning(f"Error initializing ChatOpenAI: {e}")

    # 2. Google Gemini
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_key and not gemini_key.startswith("your-"):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            logger.info("Using Google Gemini (gemini-1.5-flash) for agent reasoning.")
            return ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                temperature=0.2,
                google_api_key=gemini_key
            )
        except Exception as e:
            logger.warning(f"Error initializing ChatGoogleGenerativeAI: {e}")

    # 3. Anthropic Claude
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key and not anthropic_key.startswith("your-"):
        try:
            from langchain_anthropic import ChatAnthropic
            logger.info("Using Anthropic Claude for agent reasoning.")
            return ChatAnthropic(
                model="claude-3-5-sonnet-20240620",
                temperature=0.2,
                api_key=anthropic_key
            )
        except Exception as e:
            logger.warning(f"Error initializing ChatAnthropic: {e}")

    logger.warning("No active LLM API key detected. Running in deterministic heuristic sentiment mode.")
    return None


def emit_langsmith_trace(
    name: str,
    inputs: Dict[str, Any],
    outputs: Dict[str, Any],
    run_type: str = "chain",
    tags: Optional[List[str]] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
) -> bool:
    """
    Send an execution trace to LangSmith (https://api.smith.langchain.com/runs)
    when LANGCHAIN_TRACING_V2=true and LANGCHAIN_API_KEY is configured in .env.
    Works in both LLM mode and deterministic FinBERT/heuristic mode.
    """
    tracing_enabled = os.getenv("LANGCHAIN_TRACING_V2", "").lower() in ("true", "1", "yes")
    api_key = os.getenv("LANGCHAIN_API_KEY", "").strip()
    if not tracing_enabled or not api_key:
        return False

    project_name = os.getenv("LANGCHAIN_PROJECT", "PulsePlatform").strip() or "PulsePlatform"
    endpoint = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com").rstrip("/")
    now_iso = datetime.now(timezone.utc).isoformat()

    payload = {
        "id": str(uuid.uuid4()),
        "name": name,
        "run_type": run_type,
        "start_time": start_time or now_iso,
        "end_time": end_time or now_iso,
        "inputs": inputs,
        "outputs": outputs,
        "session_name": project_name,
        "tags": tags or ["pulse-agent"],
        "extra": {
            "metadata": {
                "platform": "Pulse Sentiment & Market Signal Platform",
                "project": project_name,
            }
        },
    }

    try:
        req = urllib.request.Request(
            f"{endpoint}/runs",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-api-key": api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status in (200, 201, 202)
    except Exception as e:
        logger.debug(f"LangSmith trace notice for {name}: {e}")
        return False


class BaseAgent(ABC):
    """Abstract base class for all Pulse data agents."""

    def __init__(self, output_dir: Optional[str] = None):
        if output_dir:
            self.output_dir = Path(output_dir)
        elif os.getenv("VERCEL"):
            self.output_dir = Path("/tmp/pulse_output")
        else:
            self.output_dir = Path(__file__).resolve().parent.parent / "output"
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            self.output_dir = Path("/tmp/pulse_output")
            self.output_dir.mkdir(parents=True, exist_ok=True)
        self.llm = get_llm()
        self._finbert = None

    @property
    def finbert(self):
        """Lazy access to the Hugging Face FinBERT financial domain scorer."""
        if self._finbert is None:
            try:
                from agents.finbert import get_finbert_scorer
                self._finbert = get_finbert_scorer()
            except Exception as e:
                logger.warning(f"Failed to load FinBERT: {e}")
                self._finbert = None
        return self._finbert

    def score_posts_with_finbert(self, posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Run Hugging Face FinBERT sequence classification across a list of posts."""
        if self.finbert and self.finbert.is_loaded:
            try:
                return self.finbert.score_posts(posts)
            except Exception as e:
                logger.warning(f"FinBERT scoring encountered error: {e}")
        return posts

    @abstractmethod
    def run(self, *args, **kwargs) -> Dict[str, Any]:
        """Execute the agent monitoring workflow and return a structured report dictionary."""
        pass

    def save_report(
        self,
        report_data: Dict[str, Any],
        topic_or_user: str,
        prefix: str = "report",
        output_file: Optional[str] = None
    ) -> Path:
        """Serialize data to a formatted JSON report in the output directory."""
        if output_file:
            path = Path(output_file)
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            safe_name = "".join(c if c.isalnum() else "_" for c in topic_or_user.lower())
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = self.output_dir / f"{prefix}_{safe_name}_{timestamp}.json"

        with open(path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        # Automatically emit a structured LangSmith trace run for this agent execution
        emit_langsmith_trace(
            name=self.__class__.__name__,
            inputs={"target": topic_or_user, "prefix": prefix},
            outputs={
                "aggregate_sentiment_score": report_data.get("aggregate_sentiment_score"),
                "overall_sentiment": report_data.get("overall_sentiment") or report_data.get("sentiment_signal"),
                "total_posts_analyzed": report_data.get("total_posts_analyzed") or report_data.get("new_posts_analyzed", 0),
                "top_themes": report_data.get("top_themes") or report_data.get("key_themes", []),
                "executive_summary": report_data.get("executive_summary", ""),
                "report_path": str(path),
            },
            run_type="chain",
            tags=["pulse-agent", prefix, self.__class__.__name__],
        )

        return path
