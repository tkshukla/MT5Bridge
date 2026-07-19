//+------------------------------------------------------------------+
//| KotakLoginPanel.mqh                                               |
//| A small CAppDialog-based panel with TOTP/MPIN CEdit fields and a   |
//| LOGIN CButton. Uses MQL5's standard Controls library instead of    |
//| raw chart OBJ_EDIT objects — raw OBJ_EDIT objects register clicks  |
//| but do not reliably take real keyboard focus on this platform (a   |
//| known limitation confirmed via diagnostic logging), whereas CEdit  |
//| inside a CAppDialog manages focus correctly.                       |
//|                                                                    |
//| TOTP/MPIN never leave this process except in the one POST to      |
//| /auth/kotak-login — see BridgeClient.mqh's BridgeKotakLogin().     |
//+------------------------------------------------------------------+
#property strict

#include <Controls\Dialog.mqh>
#include <Controls\Edit.mqh>
#include <Controls\Button.mqh>
#include <Controls\Label.mqh>
#include <MT5Bridge\BridgeClient.mqh>

class CKotakLoginPanel : public CAppDialog
  {
private:
   CLabel            m_totp_label;
   CEdit             m_totp_edit;
   CLabel            m_mpin_label;
   CEdit             m_mpin_edit;
   CButton           m_login_button;
   CLabel            m_status_label;

public:
                     CKotakLoginPanel(void) {}
                    ~CKotakLoginPanel(void) {}

   virtual bool      Create(const long chart, const string name, const int subwin,
                             const int x1, const int y1, const int x2, const int y2);
   void              OnClickLogin(void);

protected:
   bool              CreateControls(void);

   EVENT_MAP_BEGIN(CKotakLoginPanel)
   ON_EVENT(ON_CLICK, m_login_button, OnClickLogin)
   EVENT_MAP_END(CAppDialog)
  };

bool CKotakLoginPanel::Create(const long chart, const string name, const int subwin,
                               const int x1, const int y1, const int x2, const int y2)
  {
   if(!CAppDialog::Create(chart, name, subwin, x1, y1, x2, y2))
      return false;
   if(!CreateControls())
      return false;
   return true;
  }

bool CKotakLoginPanel::CreateControls(void)
  {
   int x = 10, y = 30, h = 20;

   if(!m_totp_label.Create(m_chart_id, m_name + "TotpLabel", m_subwin, x, y, x + 40, y + h))
      return false;
   m_totp_label.Text("TOTP:");
   if(!Add(m_totp_label))
      return false;

   if(!m_totp_edit.Create(m_chart_id, m_name + "TotpEdit", m_subwin, x + 42, y, x + 112, y + h))
      return false;
   if(!Add(m_totp_edit))
      return false;

   if(!m_mpin_label.Create(m_chart_id, m_name + "MpinLabel", m_subwin, x + 120, y, x + 160, y + h))
      return false;
   m_mpin_label.Text("MPIN:");
   if(!Add(m_mpin_label))
      return false;

   if(!m_mpin_edit.Create(m_chart_id, m_name + "MpinEdit", m_subwin, x + 162, y, x + 232, y + h))
      return false;
   if(!Add(m_mpin_edit))
      return false;

   if(!m_login_button.Create(m_chart_id, m_name + "LoginBtn", m_subwin, x + 240, y, x + 320, y + h + 2))
      return false;
   m_login_button.Text("LOGIN");
   if(!Add(m_login_button))
      return false;

   if(!m_status_label.Create(m_chart_id, m_name + "StatusLabel", m_subwin, x + 328, y, x + 520, y + h))
      return false;
   m_status_label.Text("Kotak: not logged in");
   if(!Add(m_status_label))
      return false;

   return true;
  }

void CKotakLoginPanel::OnClickLogin(void)
  {
   string totp = m_totp_edit.Text();
   string mpin = m_mpin_edit.Text();

   if(totp == "" || mpin == "")
     {
      m_status_label.Text("Kotak: enter TOTP + MPIN");
      return;
     }

   m_status_label.Text("Kotak: logging in...");
   ChartRedraw();

   string ucc = "";
   string error = "";
   bool ok = BridgeKotakLogin(totp, mpin, ucc, error);

   // Clear both immediately either way — TOTP is single-use regardless of outcome,
   // and there is no reason to leave MPIN sitting typed on screen.
   m_totp_edit.Text("");
   m_mpin_edit.Text("");

   if(ok)
     {
      m_status_label.Text("Kotak: logged in (" + ucc + ")");
      Print("Kotak Neo login successful, ucc=", ucc);
     }
   else
     {
      m_status_label.Text("Kotak: login failed");
      Print("Kotak Neo login failed: ", error);
      MessageBox("Kotak Neo login failed: " + error, "MT5Bridge", MB_OK | MB_ICONERROR);
     }
  }
