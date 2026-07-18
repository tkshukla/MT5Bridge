# MT5-side setup

## Files

- `Include/MT5Bridge/BridgeClient.mqh` — HTTP client wrapper (WinHTTP via MQL5's
  `WebRequest`) for all REST endpoints, plus confirmation-token minting.
- `Include/MT5Bridge/JsonHelper.mqh` — a small, purpose-built JSON value extractor
  (not a generic parser) for the specific response shapes this API returns.
- `Include/MT5Bridge/Models.mqh` — structs mirroring the API's Quote/Position/Holding/
  Portfolio/Order types.
- `Experts/MT5BridgeDashboard.mq5` — the dashboard EA: on-chart panel with holdings/
  positions/P&L display and BUY/SELL/EXIT/CLOSE/MODIFY buttons, each gated by a
  confirmation dialog.

## Important limitation: polling, not a native WebSocket

MQL5 has no built-in WebSocket client — `WebRequest()` is HTTP(S) request/response
only. Rather than fabricate a fake "WebSocket in pure MQL5" (which would require an
external DLL this repo doesn't ship), **the EA polls the REST endpoints on a timer**
(`OnTimer`, default 1s for quotes, 5s for positions/holdings/portfolio — configurable
via EA inputs). The backend's `/ws/*` endpoints exist and stream in real time for any
client that *can* speak WebSocket (e.g. a future companion desktop app), but the
MQL5 EA in this repo does not use them. If you need true push-based updates inside
MT5 itself, the standard approach is a small WinHTTP/WebSocket bridge DLL — out of
scope here; polling at 1s is indistinguishable from streaming for manual-trading
purposes.

## Setup steps

1. **Allow the bridge URL in MT5**: Tools → Options → Expert Advisors → check "Allow
   WebRequest for listed URL" and add `https://<your-vm-domain>`. `WebRequest` calls to
   any URL not on this list fail silently (return -1), so this step is not optional.
2. Copy `Include/MT5Bridge/` into `<Data Folder>/MQL5/Include/MT5Bridge/`.
3. Copy `Experts/MT5BridgeDashboard.mq5` into `<Data Folder>/MQL5/Experts/`.
4. Open in MetaEditor, compile (F7) — should produce `MT5BridgeDashboard.ex5` with no
   errors against MT5 build 3800+.
5. Attach the EA to any chart. Set inputs:
   - `InpBridgeBaseUrl`: e.g. `https://vm-host/api/v1`
   - `InpAuthToken`: a JWT obtained via your own operator login flow (this repo does
     not ship an interactive login dialog — issue tokens via `create_access_token` on
     the backend and paste the value in, or add your own login flow if you want it
     inside MT5 itself).
   - `InpQuoteSymbols`: comma-separated list of backend `symbol` values to poll quotes
     for, e.g. `NIFTY24JULFUT,BANKNIFTY24JULFUT`.
6. Confirm the panel renders on the chart and `Positions/Holdings/P&L` populate. Try a
   BUY on a small quantity in a test/demo-scoped Kotak Neo product first.

## Safety behavior baked into the EA

- Every button click opens a `MessageBox` order preview (symbol, side, quantity, order
  type, price, product) — clicking "No" aborts with zero API calls made.
- Only on "Yes" does the EA mint a confirmation token (`BridgeGenerateConfirmationToken`
  in `BridgeClient.mqh` — a random GUID-like string, never derived from anything
  predictable) and send the order request with `confirmed_at` set to the current time.
- The EA has no `OnTick`-driven order logic anywhere — check `MT5BridgeDashboard.mq5`
  yourself; the only calls to `BridgeSubmitManualOrder` /`BridgeModifyOrder` /
  `BridgeClosePosition` are inside the button-click branch of `OnChartEvent`.
