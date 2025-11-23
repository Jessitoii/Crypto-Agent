import time

class PaperExchange:
    def __init__(self, balance, app_state, log_ui, refresh_ui):
        self.balance = balance
        self.positions = {} 
        self.total_pnl = 0.0
        self.app_state = app_state
        self.log_ui = log_ui
        self.refresh_ui = refresh_ui

    def open_position(self, symbol, side, price, amount_usdt, leverage, tp_pct, sl_pct):
        if not self.app_state.is_running: return # Bot durdurulduysa işlem açma

        if symbol in self.positions:
            self.log_ui(f"⚠️ {symbol} pozisyonu zaten açık.", "warning")
            return

        if self.balance < amount_usdt:
            self.log_ui("❌ Bakiye Yetersiz!", "error")
            return

        # Hesaplamalar
        tp_price = price * (1 + tp_pct/100) if side == 'LONG' else price * (1 - tp_pct/100)
        sl_price = price * (1 - sl_pct/100) if side == 'LONG' else price * (1 + sl_pct/100)
        
        self.balance -= amount_usdt
        self.positions[symbol] = {
            'entry': price, 'qty': (amount_usdt * leverage) / price,
            'side': side, 'lev': leverage, 'margin': amount_usdt,
            'tp': tp_price, 'sl': sl_price, 'current_price': price,
            'pnl': 0.0
        }
        self.log_ui(f"🔵 POZİSYON AÇILDI: {symbol.upper()} {side} | Giriş: {price}", "info")
        self.refresh_ui() # Arayüzü güncelle

    def check_positions(self, symbol, current_price):
        if symbol not in self.positions: return
        
        pos = self.positions[symbol]
        pos['current_price'] = current_price
        
        # Anlık PnL Güncelleme (Görsel İçin)
        if pos['side'] == 'LONG':
            pos['pnl'] = (current_price - pos['entry']) * pos['qty']
        else:
            pos['pnl'] = (pos['entry'] - current_price) * pos['qty']

        # TP/SL Kontrolü
        close_reason = None
        if pos['side'] == 'LONG':
            if current_price >= pos['tp']: close_reason = "TAKE PROFIT 💰"
            elif current_price <= pos['sl']: close_reason = "STOP LOSS 🛑"
        else:
            if current_price <= pos['tp']: close_reason = "TAKE PROFIT 💰"
            elif current_price >= pos['sl']: close_reason = "STOP LOSS 🛑"

        if close_reason:
            self.close_position(symbol, close_reason, pos['pnl'])

    def close_position(self, symbol, reason, pnl):
        pos = self.positions[symbol]
        self.balance += pos['margin'] + pnl
        self.total_pnl += pnl
        del self.positions[symbol]
        
        color = "success" if pnl > 0 else "error"
        self.log_ui(f"🏁 KAPANDI: {symbol.upper()} ({reason}) | PnL: {pnl:.2f} USDT", color)
        self.refresh_ui()