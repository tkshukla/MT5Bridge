from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUEST_LATENCY = Histogram(
    "mt5bridge_http_request_latency_seconds",
    "HTTP request latency",
    ["method", "path", "status"],
)

ORDER_ACTIONS_TOTAL = Counter(
    "mt5bridge_order_actions_total",
    "Manual order actions processed",
    ["action", "result"],
)

TICKS_RECEIVED_TOTAL = Counter(
    "mt5bridge_ticks_received_total",
    "Ticks received from the Kotak Neo feed",
    ["symbol"],
)

KOTAK_FEED_CONNECTED = Gauge(
    "mt5bridge_kotak_feed_connected",
    "1 if the Kotak Neo WebSocket feed is currently connected, else 0",
)

WS_CLIENTS_CONNECTED = Gauge(
    "mt5bridge_ws_clients_connected",
    "Currently connected WebSocket clients",
    ["endpoint"],
)
