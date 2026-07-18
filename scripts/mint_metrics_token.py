#!/usr/bin/env python3
"""
Mints a long-lived, viewer-scope JWT for Prometheus to scrape /metrics with, and writes
it to monitoring/metrics_token (git-ignored). Run this once during setup, and again if
you ever rotate JWT_SECRET_KEY.

Usage (from the backend/ directory, with the venv/deps installed):
    python ../scripts/mint_metrics_token.py [--days 365]
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from jose import jwt  # noqa: E402

from app.config import get_settings  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--days", type=int, default=365)
args = parser.parse_args()

settings = get_settings()
expire = datetime.now(timezone.utc) + timedelta(days=args.days)
token = jwt.encode(
    {"sub": "prometheus", "role": "viewer", "exp": expire, "type": "access"},
    settings.jwt_secret_key,
    algorithm=settings.jwt_algorithm,
)

out_path = Path(__file__).resolve().parents[1] / "monitoring" / "metrics_token"
out_path.write_text(token, encoding="utf-8")
print(f"Wrote metrics token (expires {expire.isoformat()}) to {out_path}")
