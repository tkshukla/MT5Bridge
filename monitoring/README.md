# Monitoring

- `prometheus.yml` scrapes `backend:8000/metrics` every 10s, authenticated with a
  long-lived viewer-scope JWT (see `scripts/mint_metrics_token.py` — `scripts/setup.sh`
  runs this automatically on first provisioning if `monitoring/metrics_token` doesn't
  exist yet).
- `grafana/provisioning/datasources/datasource.yml` wires Grafana to that Prometheus
  automatically (no manual "Add data source" step).
- `grafana/provisioning/dashboards/json/mt5bridge_overview.json` is auto-loaded into
  the "MT5Bridge" folder: API latency (p95), API up/down, Kotak Neo feed connectivity,
  tick rate by symbol, WebSocket client counts, order action rate by result, and 5xx
  error rate.
- Grafana is reachable at `http://<vm-host>:3000` (bind to `127.0.0.1` only per
  `docker-compose.yml` — use an SSH tunnel or put it behind Nginx + auth if you want
  remote access; it is not exposed by `nginx/mt5bridge.conf` by default).
- Metrics defined in `backend/app/metrics.py`: `mt5bridge_http_request_latency_seconds`,
  `mt5bridge_order_actions_total`, `mt5bridge_ticks_received_total`,
  `mt5bridge_kotak_feed_connected`, `mt5bridge_ws_clients_connected`.
