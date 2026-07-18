//+------------------------------------------------------------------+
//| MT5BridgeDashboard.mq5                                             |
//| MT5-side dashboard for the Kotak Neo bridge: displays quotes,      |
//| positions, holdings and P&L, and offers BUY/SELL/EXIT/CLOSE/       |
//| MODIFY buttons — each gated by an explicit confirmation dialog.    |
//|                                                                     |
//| SAFETY: there is no OnTick-driven order logic anywhere in this     |
//| file. Every call to BridgeSubmitManualOrder / BridgeModifyOrder /   |
//| BridgeClosePosition happens inside OnChartEvent, after the user    |
//| clicks "Yes" on a MessageBox order preview. See docs/SECURITY.md   |
//| in the repo root.                                                  |
//+------------------------------------------------------------------+
#property copyright "MT5Bridge"
#property version   "1.00"
#property strict

#include <MT5Bridge\BridgeClient.mqh>
#include <MT5Bridge\Models.mqh>

input string InpBridgeBaseUrl      = "https://your-vm-host/api/v1";
input string InpAuthToken          = "";                          // JWT — see mql5/README.md
input string InpQuoteSymbols        = "NIFTY24JULFUT";              // comma-separated backend symbols
input string InpDefaultSymbol       = "NIFTY24JULFUT";
input string InpDefaultProduct      = "MIS";
input int    InpDefaultQuantity     = 50;
input int    InpQuotePollSeconds    = 1;
input int    InpPortfolioPollSeconds = 5;

#define PANEL_PREFIX "MT5B_"

datetime g_last_quote_poll = 0;
datetime g_last_portfolio_poll = 0;

string   g_quote_symbols[];

//+------------------------------------------------------------------+
int OnInit()
  {
   BridgeInit(InpBridgeBaseUrl, InpAuthToken);

   int n = StringSplit(InpQuoteSymbols, ',', g_quote_symbols);
   if(n <= 0)
     {
      ArrayResize(g_quote_symbols, 1);
      g_quote_symbols[0] = InpDefaultSymbol;
     }

   BuildPanel();
   EventSetTimer(1);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   ObjectsDeleteAll(0, PANEL_PREFIX);
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   // Intentionally empty: this EA never places, modifies, or closes orders from
   // OnTick. All order actions originate exclusively from OnChartEvent button
   // clicks, after user confirmation. See docs/SECURITY.md.
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   datetime now = TimeLocal();

   if(now - g_last_quote_poll >= InpQuotePollSeconds)
     {
      RefreshQuotes();
      g_last_quote_poll = now;
     }

   if(now - g_last_portfolio_poll >= InpPortfolioPollSeconds)
     {
      RefreshPositions();
      RefreshHoldings();
      RefreshPortfolio();
      g_last_portfolio_poll = now;
     }
  }

//+------------------------------------------------------------------+
//| Panel construction                                                 |
//+------------------------------------------------------------------+
void BuildPanel()
  {
   CreateLabel(PANEL_PREFIX + "title", "MT5Bridge — Kotak Neo (manual orders only)", 10, 10, clrWhite);
   CreateLabel(PANEL_PREFIX + "quote", "Quote: ...", 10, 30, clrSilver);
   CreateLabel(PANEL_PREFIX + "position", "Position: ...", 10, 50, clrSilver);
   CreateLabel(PANEL_PREFIX + "holding", "Holding: ...", 10, 70, clrSilver);
   CreateLabel(PANEL_PREFIX + "portfolio", "Portfolio: ...", 10, 90, clrSilver);

   CreateButton(PANEL_PREFIX + "btn_buy", "BUY", 10, 120, 80, 26, clrLime);
   CreateButton(PANEL_PREFIX + "btn_sell", "SELL", 100, 120, 80, 26, clrTomato);
   CreateButton(PANEL_PREFIX + "btn_exit", "EXIT", 190, 120, 80, 26, clrOrange);
   CreateButton(PANEL_PREFIX + "btn_close", "CLOSE POSITION", 280, 120, 130, 26, clrGold);
   CreateButton(PANEL_PREFIX + "btn_modify", "MODIFY ORDER", 420, 120, 130, 26, clrDodgerBlue);
  }

void CreateLabel(const string name, const string text, int x, int y, color clr)
  {
   ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 9);
  }

void CreateButton(const string name, const string text, int x, int y, int w, int h, color clr)
  {
   ObjectCreate(0, name, OBJ_BUTTON, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, name, OBJPROP_XSIZE, w);
   ObjectSetInteger(0, name, OBJPROP_YSIZE, h);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetInteger(0, name, OBJPROP_BGCOLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clrBlack);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
  }

//+------------------------------------------------------------------+
//| Data refresh                                                       |
//+------------------------------------------------------------------+
void RefreshQuotes()
  {
   BridgeQuote q;
   string text = "Quote: ";
   for(int i = 0; i < ArraySize(g_quote_symbols); i++)
     {
      if(BridgeGetQuote(g_quote_symbols[i], q))
         text += StringFormat("%s=%.2f  ", q.symbol, q.ltp);
     }
   ObjectSetString(0, PANEL_PREFIX + "quote", OBJPROP_TEXT, text);
  }

void RefreshPositions()
  {
   BridgePosition positions[];
   int n = BridgeGetPositions(positions);
   string text = StringFormat("Position (%d): ", n);
   for(int i = 0; i < n && i < 3; i++)
      text += StringFormat("%s %s qty=%d uPnL=%.2f  ", positions[i].symbol, positions[i].product,
                            positions[i].quantity, positions[i].unrealized_pnl);
   ObjectSetString(0, PANEL_PREFIX + "position", OBJPROP_TEXT, text);
  }

void RefreshHoldings()
  {
   BridgeHolding holdings[];
   int n = BridgeGetHoldings(holdings);
   string text = StringFormat("Holding (%d): ", n);
   for(int i = 0; i < n && i < 3; i++)
      text += StringFormat("%s qty=%d pnl=%.2f  ", holdings[i].symbol, holdings[i].quantity, holdings[i].pnl);
   ObjectSetString(0, PANEL_PREFIX + "holding", OBJPROP_TEXT, text);
  }

void RefreshPortfolio()
  {
   BridgePortfolio p;
   if(BridgeGetPortfolio(p))
     {
      string text = StringFormat("Portfolio: value=%.2f cash=%.2f dayPnL=%.2f openPnL=%.2f",
                                  p.total_value, p.cash_available, p.day_pnl, p.open_pnl);
      ObjectSetString(0, PANEL_PREFIX + "portfolio", OBJPROP_TEXT, text);
     }
  }

//+------------------------------------------------------------------+
//| Button handling — the ONLY place order actions originate from     |
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
  {
   if(id != CHARTEVENT_OBJECT_CLICK)
      return;

   if(sparam == PANEL_PREFIX + "btn_buy")
      HandleManualOrderClick(BRIDGE_SIDE_BUY);
   else if(sparam == PANEL_PREFIX + "btn_sell")
      HandleManualOrderClick(BRIDGE_SIDE_SELL);
   else if(sparam == PANEL_PREFIX + "btn_exit")
      HandleClosePositionClick();
   else if(sparam == PANEL_PREFIX + "btn_close")
      HandleClosePositionClick();
   else if(sparam == PANEL_PREFIX + "btn_modify")
      HandleModifyOrderClick();

   // Release button visual "pressed" state
   if(ObjectFind(0, sparam) >= 0 && ObjectGetInteger(0, sparam, OBJPROP_TYPE) == OBJ_BUTTON)
      ObjectSetInteger(0, sparam, OBJPROP_STATE, false);
  }

void HandleManualOrderClick(ENUM_BRIDGE_SIDE side)
  {
   string symbol = InpDefaultSymbol;
   int quantity = InpDefaultQuantity;
   string product = InpDefaultProduct;
   string order_type = "MARKET";
   double price = 0.0;

   string preview = StringFormat(
      "Confirm MANUAL ORDER\n\nSymbol: %s\nSide: %s\nQuantity: %d\nType: %s\nProduct: %s\n\n"
      "This will place a REAL order via Kotak Neo. Continue?",
      symbol, BridgeSideToString(side), quantity, order_type, product);

   int result = MessageBox(preview, "MT5Bridge — Order Confirmation", MB_YESNO | MB_ICONWARNING | MB_DEFBUTTON2);
   if(result != IDYES)
     {
      Print("Manual order cancelled by user at confirmation dialog.");
      return;
     }

   string token = BridgeGenerateConfirmationToken();
   BridgeOrderResult res = BridgeSubmitManualOrder(symbol, side, quantity, order_type, price, product, token);

   if(res.success)
      Print("Manual order placed: ", res.order_id, " status=", res.status);
   else
     {
      Print("Manual order rejected: http=", res.http_status, " reason=", res.reject_reason);
      MessageBox("Order rejected: " + res.reject_reason, "MT5Bridge", MB_OK | MB_ICONERROR);
     }
  }

void HandleClosePositionClick()
  {
   string symbol = InpDefaultSymbol;
   string product = InpDefaultProduct;

   string preview = StringFormat(
      "Confirm CLOSE POSITION\n\nSymbol: %s\nProduct: %s\n\nThis will close the entire open position at "
      "market via Kotak Neo. Continue?",
      symbol, product);

   int result = MessageBox(preview, "MT5Bridge — Close Confirmation", MB_YESNO | MB_ICONWARNING | MB_DEFBUTTON2);
   if(result != IDYES)
     {
      Print("Close position cancelled by user at confirmation dialog.");
      return;
     }

   string token = BridgeGenerateConfirmationToken();
   BridgeOrderResult res = BridgeClosePosition(symbol, product, token);

   if(res.success)
      Print("Position close submitted: ", res.order_id, " status=", res.status);
   else
     {
      Print("Position close rejected: http=", res.http_status, " reason=", res.reject_reason);
      MessageBox("Close rejected: " + res.reject_reason, "MT5Bridge", MB_OK | MB_ICONERROR);
     }
  }

void HandleModifyOrderClick()
  {
   string order_id_str = "";
   if(!InputBoxSimulate("Enter Kotak Neo order id to modify:", order_id_str))
      return;

   string qty_str = "";
   InputBoxSimulate("New quantity (blank = unchanged):", qty_str);
   string price_str = "";
   InputBoxSimulate("New price (blank = unchanged):", price_str);

   int new_qty = (qty_str == "" ? InpDefaultQuantity : (int)StringToInteger(qty_str));
   double new_price = (price_str == "" ? 0.0 : StringToDouble(price_str));

   string preview = StringFormat(
      "Confirm MODIFY ORDER\n\nOrder ID: %s\nNew Quantity: %d\nNew Price: %.2f\n\nContinue?",
      order_id_str, new_qty, new_price);

   int result = MessageBox(preview, "MT5Bridge — Modify Confirmation", MB_YESNO | MB_ICONWARNING | MB_DEFBUTTON2);
   if(result != IDYES)
     {
      Print("Modify order cancelled by user at confirmation dialog.");
      return;
     }

   string token = BridgeGenerateConfirmationToken();
   BridgeOrderResult res = BridgeModifyOrder(order_id_str, new_qty, new_price, token);

   if(res.success)
      Print("Order modified: ", res.order_id, " status=", res.status);
   else
     {
      Print("Order modify rejected: http=", res.http_status, " reason=", res.reject_reason);
      MessageBox("Modify rejected: " + res.reject_reason, "MT5Bridge", MB_OK | MB_ICONERROR);
     }
  }

//--- MQL5 has no built-in text input dialog; this is a minimal stand-in using
//--- MessageBox-driven confirmation of a fixed prompt. Replace with a proper custom
//--- OBJ_EDIT-based dialog if you need real free-text input for order id/qty/price.
bool InputBoxSimulate(const string prompt, string &out_value)
  {
   Print(prompt, " (edit InpDefaultQuantity/order id inputs on the EA property panel, then re-run)");
   out_value = "";
   return true;
  }
