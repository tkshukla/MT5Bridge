//+------------------------------------------------------------------+
//| BridgeClient.mqh — REST client for the MT5Bridge backend.         |
//| Uses MQL5's WebRequest() (HTTP/HTTPS request-response only — see  |
//| mql5/README.md for why this is polling, not a real WebSocket).    |
//|                                                                    |
//| IMPORTANT: the target base URL must be added under Tools > Options |
//| > Expert Advisors > "Allow WebRequest for listed URL", or every    |
//| call here fails with WebRequest returning -1 / GetLastError 4060.  |
//+------------------------------------------------------------------+
#property strict

#include <MT5Bridge\JsonHelper.mqh>
#include <MT5Bridge\Models.mqh>

string g_bridge_base_url = "";
string g_bridge_auth_token = "";
int    g_bridge_timeout_ms = 5000;

void BridgeInit(const string base_url, const string auth_token, int timeout_ms = 5000)
  {
   g_bridge_base_url = base_url;
   g_bridge_auth_token = auth_token;
   g_bridge_timeout_ms = timeout_ms;
  }

//--- Generates a random, unpredictable token — minted ONLY when this function is
//--- called from inside a confirmed button-click handler. See docs/SECURITY.md.
string BridgeGenerateConfirmationToken()
  {
   MathSrand(GetTickCount() ^ (int)AccountInfoInteger(ACCOUNT_LOGIN) ^ (int)TimeLocal());
   string token = "";
   string charset = "0123456789abcdef";
   for(int i = 0; i < 32; i++)
     {
      int idx = MathRand() % StringLen(charset);
      token += StringSubstr(charset, idx, 1);
     }
   return token;
  }

string BridgeNowIso8601()
  {
   datetime now = TimeGMT();
   return TimeToString(now, TIME_DATE) + "T" + TimeToString(now, TIME_SECONDS) + "Z";
  }

//--- Low-level request. method: "GET"/"POST"/"PUT". path e.g. "/positions".
//--- Returns HTTP status code (or -1 on transport failure); response body via out param.
int BridgeRawRequest(const string method, const string path, const string json_body, string &response_body)
  {
   string url = g_bridge_base_url + path;
   string headers = "Content-Type: application/json\r\n";
   if(g_bridge_auth_token != "")
      headers += "Authorization: Bearer " + g_bridge_auth_token + "\r\n";

   uchar post_data[];
   if(json_body != "")
     {
      int len = StringToCharArray(json_body, post_data, 0, WHOLE_ARRAY, CP_UTF8) - 1;
      ArrayResize(post_data, MathMax(len, 0));
     }
   else
      ArrayResize(post_data, 0);

   uchar result[];
   string result_headers;

   ResetLastError();
   int status = WebRequest(method, url, headers, g_bridge_timeout_ms, post_data, result, result_headers);

   if(status == -1)
     {
      int err = GetLastError();
      Print("BridgeRawRequest failed: ", method, " ", url, " error=", err,
            " (4060 = URL not in Options > Expert Advisors allow-list)");
      response_body = "";
      return -1;
     }

   response_body = CharArrayToString(result, 0, WHOLE_ARRAY, CP_UTF8);
   return status;
  }

int BridgeGet(const string path, string &response_body)
  {
   return BridgeRawRequest("GET", path, "", response_body);
  }

int BridgePost(const string path, const string json_body, string &response_body)
  {
   return BridgeRawRequest("POST", path, json_body, response_body);
  }

//--- Read endpoints --------------------------------------------------------

bool BridgeGetQuote(const string symbol, BridgeQuote &out_quote)
  {
   string body;
   int status = BridgeGet("/quotes/" + symbol, body);
   if(status != 200)
      return false;
   out_quote.symbol = symbol;
   out_quote.ltp = JsonGetDouble(body, "ltp");
   out_quote.bid = JsonGetDouble(body, "bid");
   out_quote.ask = JsonGetDouble(body, "ask");
   out_quote.volume = JsonGetLong(body, "volume");
   out_quote.ts = JsonGetString(body, "ts");
   return true;
  }

int BridgeGetPositions(BridgePosition &out_positions[])
  {
   string body;
   int status = BridgeGet("/positions", body);
   if(status != 200)
     {
      ArrayResize(out_positions, 0);
      return 0;
     }
   string objects[];
   int n = JsonSplitArrayObjects(body, objects);
   ArrayResize(out_positions, n);
   for(int i = 0; i < n; i++)
     {
      out_positions[i].symbol = JsonGetString(objects[i], "symbol");
      out_positions[i].product = JsonGetString(objects[i], "product");
      out_positions[i].quantity = (int)JsonGetLong(objects[i], "quantity");
      out_positions[i].avg_price = JsonGetDouble(objects[i], "avg_price");
      out_positions[i].ltp = JsonGetDouble(objects[i], "ltp");
      out_positions[i].unrealized_pnl = JsonGetDouble(objects[i], "unrealized_pnl");
      out_positions[i].realized_pnl = JsonGetDouble(objects[i], "realized_pnl");
     }
   return n;
  }

int BridgeGetHoldings(BridgeHolding &out_holdings[])
  {
   string body;
   int status = BridgeGet("/holdings", body);
   if(status != 200)
     {
      ArrayResize(out_holdings, 0);
      return 0;
     }
   string objects[];
   int n = JsonSplitArrayObjects(body, objects);
   ArrayResize(out_holdings, n);
   for(int i = 0; i < n; i++)
     {
      out_holdings[i].symbol = JsonGetString(objects[i], "symbol");
      out_holdings[i].quantity = (int)JsonGetLong(objects[i], "quantity");
      out_holdings[i].avg_price = JsonGetDouble(objects[i], "avg_price");
      out_holdings[i].ltp = JsonGetDouble(objects[i], "ltp");
      out_holdings[i].current_value = JsonGetDouble(objects[i], "current_value");
      out_holdings[i].pnl = JsonGetDouble(objects[i], "pnl");
     }
   return n;
  }

bool BridgeGetPortfolio(BridgePortfolio &out_portfolio)
  {
   string body;
   int status = BridgeGet("/portfolio", body);
   if(status != 200)
      return false;
   out_portfolio.total_value = JsonGetDouble(body, "total_value");
   out_portfolio.cash_available = JsonGetDouble(body, "cash_available");
   out_portfolio.margin_used = JsonGetDouble(body, "margin_used");
   out_portfolio.day_pnl = JsonGetDouble(body, "day_pnl");
   out_portfolio.open_pnl = JsonGetDouble(body, "open_pnl");
   out_portfolio.realized_pnl = JsonGetDouble(body, "realized_pnl");
   return true;
  }

//--- Manual order endpoints — every call here must be preceded by a user-confirmed
//--- MessageBox in the calling EA. This client performs no confirmation itself; it
//--- only transmits whatever confirmation_token/confirmed_at it is given.

BridgeOrderResult BridgeSubmitManualOrder(const string symbol, ENUM_BRIDGE_SIDE side, int quantity,
                                           const string order_type, double price, const string product,
                                           const string confirmation_token)
  {
   BridgeOrderResult res;
   res.success = false;

   string json = StringFormat(
      "{\"symbol\":\"%s\",\"side\":\"%s\",\"quantity\":%d,\"order_type\":\"%s\","
      "\"price\":%s,\"product\":\"%s\",\"confirmation_token\":\"%s\",\"confirmed_at\":\"%s\"}",
      symbol, BridgeSideToString(side), quantity, order_type,
      (order_type == "MARKET" ? "null" : DoubleToString(price, 2)),
      product, confirmation_token, BridgeNowIso8601());

   string body;
   int status = BridgePost("/manual-order", json, body);
   res.http_status = status;
   res.order_id = JsonGetString(body, "kotak_order_id");
   res.status = JsonGetString(body, "status");
   res.reject_reason = JsonGetString(body, "reject_reason");
   res.success = (status == 201);
   return res;
  }

BridgeOrderResult BridgeModifyOrder(const string order_id, int new_quantity, double new_price,
                                     const string confirmation_token)
  {
   BridgeOrderResult res;
   res.success = false;

   string json = StringFormat(
      "{\"order_id\":\"%s\",\"quantity\":%d,\"price\":%s,\"confirmation_token\":\"%s\",\"confirmed_at\":\"%s\"}",
      order_id, new_quantity, DoubleToString(new_price, 2), confirmation_token, BridgeNowIso8601());

   string body;
   int status = BridgePost("/modify-order", json, body);
   res.http_status = status;
   res.order_id = JsonGetString(body, "kotak_order_id");
   res.status = JsonGetString(body, "status");
   res.reject_reason = JsonGetString(body, "reject_reason");
   res.success = (status == 200);
   return res;
  }

BridgeOrderResult BridgeClosePosition(const string symbol, const string product, const string confirmation_token)
  {
   BridgeOrderResult res;
   res.success = false;

   string json = StringFormat(
      "{\"symbol\":\"%s\",\"product\":\"%s\",\"confirmation_token\":\"%s\",\"confirmed_at\":\"%s\"}",
      symbol, product, confirmation_token, BridgeNowIso8601());

   string body;
   int status = BridgePost("/close-position", json, body);
   res.http_status = status;
   res.order_id = JsonGetString(body, "kotak_order_id");
   res.status = JsonGetString(body, "status");
   res.reject_reason = JsonGetString(body, "reject_reason");
   res.success = (status == 200);
   return res;
  }
