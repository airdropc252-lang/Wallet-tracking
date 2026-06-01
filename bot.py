import requests
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TELEGRAM_TOKEN = "8807718291:AAH5Ytj7tHmvAQgepKdjacR-Smn_73sxngY"
TELEGRAM_CHAT_ID = "7056939861"
HELIUS_API_KEY = "5ddc9539-90ae-419b-8ab1-fc1677cdb01e"

WALLETS = {
    "Stigman": "8fsKLLtvKNanL4ginCaiRS6UfeemY11rSf8U8fN1dJw4",
    "Cupseyy": "2fg5QD1eD7rzNNCsvnhmXFm5hqNgwTTG8p7kQ6f3rx6f"
}

bot_aktif = True
tx_history = {wallet: set() for wallet in WALLETS.values()}

def get_transactions(wallet):
    url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions?api-key={HELIUS_API_KEY}&limit=10"
    try:
        r = requests.get(url, timeout=10)
        return r.json()
    except:
        return []

def parse_tx(tx, name):
    try:
        sig = tx.get("signature", "")
        tx_type = tx.get("type", "UNKNOWN")
        desc = tx.get("description", "")

        if tx_type in ["SWAP", "TRANSFER", "TOKEN_MINT"]:
            token = "UNKNOWN"
            amount = "?"

            token_transfers = tx.get("tokenTransfers", [])
            if token_transfers:
                token = token_transfers[0].get("mint", "UNKNOWN")[-6:]
                amount = token_transfers[0].get("tokenAmount", "?")

            native = tx.get("nativeTransfers", [])
            sol_amount = "?"
            if native:
                sol_amount = round(native[0].get("amount", 0) / 1e9, 4)

            return {
                "sig": sig,
                "type": tx_type,
                "token": token,
                "amount": sol_amount,
                "desc": desc
            }
        return None
    except:
        return None

async def monitor_wallets(app):
    while True:
        try:
            if not bot_aktif:
                await asyncio.sleep(10)
                continue

            for name, wallet in WALLETS.items():
                txs = get_transactions(wallet)
                if not txs or not isinstance(txs, list):
                    continue

                for tx in txs[:5]:
                    sig = tx.get("signature", "")
                    if sig and sig not in tx_history[wallet]:
                        parsed = parse_tx(tx, name)
                        if parsed:
                            pesan = f"""🚨 Wallet Activity

Wallet: {name}
Action: {parsed['type']}
Token: {parsed['token']}
Amount: {parsed['amount']} SOL

Tx: https://solscan.io/tx/{parsed['sig']}"""
                            await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=pesan)
                        tx_history[wallet].add(sig)

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
