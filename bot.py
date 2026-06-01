import requests
import asyncio
import time
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TELEGRAM_TOKEN = "8807718291:AAGEjy4sbkDocV-GOhmuilEzIcGZVPRwmvU"
TELEGRAM_CHAT_ID = "7056939861"

WALLETS = {
    "Stigman": "8fsKLLtvKNanL4ginCaiRS6UfeemY11rSf8U8fN1dJw4",
    "Cupseyy": "2fg5QD1eD7rzNNCsvnhmXFm5hqNgwTTG8p7kQ6f3rx6f"
}

bot_aktif = True
tx_history = {}

def get_wallet_transactions(wallet):
    url = f"https://api.solscan.io/api/v2/account/transactions?account={wallet}&limit=10"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if data.get("success"):
            return data.get("data", {}).get("tx", [])
        return []
    except:
        return []

def parse_transaction(tx_data):
    try:
        if not tx_data:
            return None
        sig = tx_data.get("txHash", "")
        action = tx_data.get("type", "UNKNOWN")
        token = tx_data.get("tokenSymbol", "UNKNOWN") or tx_data.get("symbol", "UNKNOWN")
        amount = tx_data.get("amount", "?")
        
        if action not in ["SWAP", "BUY", "SELL"]:
            return None
        
        return {"tx": sig, "action": action, "token": token, "amount": amount}
    except:
        return None

async def monitor_wallets(app):
    global bot_aktif
    while True:
        try:
            if not bot_aktif:
                await asyncio.sleep(10)
                continue
            for name, wallet in WALLETS.items():
                txs = get_wallet_transactions(wallet)
                if wallet not in tx_history:
                    tx_history[wallet] = []
                for tx in txs[:5]:
                    tx_hash = tx.get("txHash", "")
                    if tx_hash not in tx_history[wallet]:
                        parsed = parse_transaction(tx)
                        if parsed:
                            pesan = f"""🚨 Wallet Activity

Wallet: {name}
Action: {parsed['action']}
Token: {parsed['token']}
Amount: {parsed['amount']} SOL

Tx: https://solscan.io/tx/{parsed['tx']}"""
                            await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=pesan)
                            tx_history[wallet].append(tx_hash)
            await asyncio.sleep(30)
        except Exception as e:
            print(f"Error: {e}")
            await asyncio.sleep(10)

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "✅ Aktif" if bot_aktif else "⛔ Berhenti"
    pesan = f"👁️ Wallet Tracker: {status}\n\n"
    for name in WALLETS.keys():
        pesan += f"• {name}\n"
    await update.message.reply_text(pesan)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_aktif
    bot_aktif = True
    await update.message.reply_text("✅ Bot aktif!")

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_aktif
    bot_aktif = False
    await update.message.reply_text("⛔ Bot berhenti!")

async def main():
    print("Wallet Tracker Bot")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stop", cmd_stop))
    async with app:
        await app.start()
        await app.updater.start_polling()
        await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID,
            text="👁️ Wallet Tracker AKTIF!\n\nMonitoring:\n• Stigman\n• Cupseyy\n\n/status /start /stop")
        await monitor_wallets(app)
        await app.updater.stop()
        await app.stop()

asyncio.run(main())
