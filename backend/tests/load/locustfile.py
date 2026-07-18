"""
Basic load test for the read-path endpoints (the ones expected to be polled/streamed
frequently by MT5). Order endpoints are deliberately NOT load-tested here — they are
low-frequency, human-confirmed actions, not something to stress-test for throughput.

Usage:
    locust -f tests/load/locustfile.py --host https://your-vm-host/api/v1
"""

import os

from locust import HttpUser, between, task

TEST_JWT = os.environ.get("LOAD_TEST_JWT", "")


class ReadPathUser(HttpUser):
    wait_time = between(0.2, 1.0)

    def on_start(self):
        self.client.headers.update({"Authorization": f"Bearer {TEST_JWT}"})

    @task(5)
    def get_quote(self):
        self.client.get("/quotes/NIFTY24JULFUT", name="/quotes/[symbol]")

    @task(3)
    def get_positions(self):
        self.client.get("/positions")

    @task(2)
    def get_portfolio(self):
        self.client.get("/portfolio")

    @task(1)
    def get_ohlc(self):
        self.client.get("/ohlc/NIFTY24JULFUT?timeframe=5m", name="/ohlc/[symbol]")

    @task(1)
    def health(self):
        self.client.get("/health")
