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

STABLE_TOKENS = ["So11111111111111111111111111111111111111112", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"]

bot_aktif = True
tx_history = {wallet: set() for wallet in WALLETS.values()}

def get_transactions(wallet):
    url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions?api-key={HELIUS_API_KEY}&limit=10"
    try:
        r = requests.get(url, timeout=10)
        return r.json()
    except:
        return []

def parse_tx(tx):
    try:
        sig = tx.get("signature", "")
        tx_type = tx.get("type", "")

        if tx_type != "SWAP":
            return None

        token_transfers = tx.get("tokenTransfers", [])
        native_transfers = tx.get("nativeTransfers", [])

        token_in = None
        token_out = None
        amount_in = 0
        amount_out = 0

        for t in token_transfers:
            mint = t.get("mint", "")
            amount = t.get("tokenAmount", 0)
            if t.get("toUserAccount") == tx.get("feePayer"):
                token_in = mint
                amount_in = amount
            elif t.get("fromUserAccount") == tx.get("feePayer"):
                token_out = mint
                amount_out = amount

        sol_in = sum(t.get("amount", 0) for t in native_transfers if t.get("toUserAccount") == tx.get("feePayer")) / 1e9
        sol_out = sum(t.get("amount", 0) for t in native_transfers if t.get("fromUserAccount") == tx.get("feePayer")) / 1e9

        if sol_out > 0.001 and token_in and token_in not in STABLE_TOKENS:
            return {
                "sig": sig,
                "action": "BUY",
                "token": token_in[-6:],
                "sol": round(sol_out, 4)
            }
        elif token_out and token_out not in STABLE_TOKENS and (sol_in > 0.001 or token_in in STABLE_TOKENS):
            return {
                "sig": sig,
                "action": "SELL",
                "token": token_out[-6:],
                "sol": round(sol_in, 4) if sol_in > 0 else round(float(amount_in), 4)
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
                        parsed = parse_tx(tx)
                        if parsed:
                            if parsed["action"] == "BUY":
                                emoji = "🟢🚀"
                                action_text = "BUY"
                            else:
                                emoji = "🔴💰"
                                action_text = "SELL"

                            waktu = datetime.now().strftime("%H:%M:%S")
                            pesan = f"""{emoji} *Wallet Alert!*

👤 *Wallet:* {name}
📊 *Action:* {action_text}
🪙 *Token:* ...{parsed['token']}
💵 *SOL:* {parsed['sol']} SOL
🕐 *Time:* {waktu}

🔗 [Lihat Transaksi](https://solscan.io/tx/{parsed['sig']})"""

                            await app.bot.send_message(
                                chat_id=TELEGRAM_CHAT_ID,
                                text=pesan,
                                parse_mode="Markdown"
                            )
                        tx_history[wallet].add(sig)

            await asyncio.sleep(30)
        except Exception as e:
            print(f"Error: {e}")
            await asyncio.sleep(10)

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "✅ Aktif" if bot_aktif else "⛔ Berhenti"
    pesan = f"👁️ *Wallet Tracker*: {status}\n\n"
    for name in WALLETS.keys():
        pesan += f"• {name}\n"
    await update.message.reply_text(pesan, parse_mode="Markdown")

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
            text="👁️ *Wallet Tracker AKTIF!*\n\nMonitoring:\n• Stigman 🐋\n• Cupseyy 🐋\n\n/status /start /stop",
            parse_mode="Markdown")
        await monitor_wallets(app)
        await app.updater.stop()
        await app.stop()

asyncio.run(main())
