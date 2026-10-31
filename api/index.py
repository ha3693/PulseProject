"""
Vercel Python Service Entrypoint for the Pulse Multi-Agent Orchestrator (`app` service).
Exposes HTTP endpoints for the internal `app` service bound to `frontend` via `AGENT_SERVICE_URL`:
  - GET  /health : Service health check
  - POST /ingest : Triggers `PulseIngestionOrchestrator` across 1 or all 14 topics and syncs to Supabase
"""

import os
import sys
import json
from pathlib import Path
from http.server import BaseHTTPRequestHandler

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agents.scheduler import PulseIngestionOrchestrator


class handler(BaseHTTPRequestHandler):
    """Vercel Python Runtime HTTP handler."""

    def _send_json(self, status_code: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send_json(
            200,
            {
                "status": "ok",
                "service": "app",
                "runtime": "python",
                "agents": [
                    "yahoo",
                    "reddit",
                    "stocktwits",
                    "bluesky",
                    "gdelt",
                    "reddit-user",
                    "stocktwits-user",
                    "bluesky-user",
                ],
            },
        )

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
            body = json.loads(raw_body) if raw_body else {}
        except Exception:
            body = {}

        topic = body.get("topic")
        if topic and str(topic).strip().upper() == "ALL":
            topic = None
        trigger = body.get("trigger", "vercel_service_binding")

        try:
            orchestrator = PulseIngestionOrchestrator(use_mock=False)
            snapshot = orchestrator.run_pipeline(
                topic_filter=topic,
                trigger_source=trigger,
                sync_db=True,
            )
            self._send_json(
                200,
                {
                    "status": "completed",
                    "topic": topic or "ALL (14 Topics)",
                    "snapshot": snapshot,
                },
            )
        except Exception as exc:
            self._send_json(
                500,
                {
                    "status": "error",
                    "message": str(exc),
                },
            )

