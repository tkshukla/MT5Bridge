//+------------------------------------------------------------------+
//| Models.mqh — structs mirroring the MT5Bridge REST API shapes.     |
//| See docs/API.md in the repo root for the authoritative schema.    |
//+------------------------------------------------------------------+
#property strict

struct BridgeQuote
  {
   string            symbol;
   double            ltp;
   double            bid;
   double            ask;
   long              volume;
   string            ts;
  };

struct BridgePosition
  {
   string            symbol;
   string            product;
   int               quantity;
   double            avg_price;
   double            ltp;
   double            unrealized_pnl;
   double            realized_pnl;
  };

struct BridgeHolding
  {
   string            symbol;
   int               quantity;
   double            avg_price;
   double            ltp;
   double            current_value;
   double            pnl;
  };

struct BridgePortfolio
  {
   double            total_value;
   double            cash_available;
   double            margin_used;
   double            day_pnl;
   double            open_pnl;
   double            realized_pnl;
  };

struct BridgeOrderResult
  {
   bool              success;
   string            order_id;
   string            status;
   string            reject_reason;
   int               http_status;
  };

enum ENUM_BRIDGE_SIDE
  {
   BRIDGE_SIDE_BUY,
   BRIDGE_SIDE_SELL
  };

string BridgeSideToString(ENUM_BRIDGE_SIDE side)
  {
   return side == BRIDGE_SIDE_BUY ? "BUY" : "SELL";
  }
