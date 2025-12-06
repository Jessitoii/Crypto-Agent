import time 
class PaperExchange:
    def __init__(self, balance):
        self.balance = balance
        self.positions = {} 
        self.total_pnl = 0.0

    def open_position(self, symbol, side, price, amount_usdt, leverage, tp_pct, sl_pct, app_state, validity):
        if not app_state.is_running: return 

        expiry_time = time.time() + (validity * 60) # Şu an + dakika
        if symbol in self.positions:
            return " Pozisyon Zaten Açık", "error"

        if self.balance < amount_usdt:
            return "❌ Bakiye Yetersiz!", "error"
        tp_price = price * (1 + tp_pct/100) if side == 'LONG' else price * (1 - tp_pct/100)
        sl_price = price * (1 - sl_pct/100) if side == 'LONG' else price * (1 + sl_pct/100)
        
        self.balance -= amount_usdt
        self.positions[symbol] = {
            'entry': price, 'qty': (amount_usdt * leverage) / price,
            'side': side, 'lev': leverage, 'margin': amount_usdt,
            'tp': tp_price, 'sl': sl_price, 'current_price': price,
            'pnl': 0.0,
            'expiry_time': expiry_time,     # <--- YENİ: Son Kullanma Tarihi
            'validity': validity
        }
        return f"🔵 POZİSYON AÇILDI: {symbol.upper()} {side} | Giriş: {price} | Top Point : {tp_pct} | Stop Loss : {sl_pct} | VM : {validity} minutes", "info"

    def check_positions(self, symbol, current_price):
<<<<<<< HEAD
        if symbol not in self.positions: return None, None, None
=======
        if symbol not in self.positions: return None, None
>>>>>>> origin
        pos = self.positions[symbol]
        pos['current_price'] = current_price
        
        if pos['side'] == 'LONG':
            pos['pnl'] = (current_price - pos['entry']) * pos['qty']
        else:
            pos['pnl'] = (pos['entry'] - current_price) * pos['qty']

        close_reason = None
        if time.time() > pos['expiry_time']:
            close_reason = "TIME LIMIT ⏳" # Zaman doldu, ne kar ne zararsa çık.
        # ---------------------------

        # Standart TP/SL Kontrolü (Aynı)
        elif pos['side'] == 'LONG':
            if current_price >= pos['tp']: close_reason = "TAKE PROFIT 💰"
            elif current_price <= pos['sl']: close_reason = "STOP LOSS 🛑"
        else:
            if current_price <= pos['tp']: close_reason = "TAKE PROFIT 💰"
            elif current_price >= pos['sl']: close_reason = "STOP LOSS 🛑"

        if close_reason:
<<<<<<< HEAD
            log, color = self.close_position(symbol, close_reason, pos['pnl'])
            return log, color, symbol
        else:
            return None, None, None
=======
            self.close_position(symbol, close_reason, pos['pnl'])
        else:
            return None, None
>>>>>>> origin

    def close_position(self, symbol, reason, pnl):
        pos = self.positions[symbol]
        self.balance += pos['margin'] + pnl
        self.total_pnl += pnl
        del self.positions[symbol]
        
        color = "success" if pnl > 0 else "error"
<<<<<<< HEAD
        return f"🏁 KAPANDI: {symbol.upper()} ({reason}) | PnL: {pnl:.2f} USDT | Enter Price: {pos['entry']} | Close Price: {pos['current_price']}", color
=======
        return f"🏁 KAPANDI: {symbol.upper()} ({reason}) | PnL: {pnl:.2f} USDT", color
>>>>>>> origin
