import requests
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TELEGRAM_TOKEN = "8807718291:AAH5Ytj7tHmvAQgepKdjacR-Smn_73sxngY"
TELEGRAM_CHAT_ID = "-1003734394227"
HELIUS_API_KEY = "5ddc9539-90ae-419b-8ab1-fc1677cdb01e"

MIN_WINRATE = 65
MIN_PROFIT = 5000
MIN_TRADES = 10
MIN_SOL_TRADE = 1.0

bot_aktif = True
whale_list = {}
notified_tx = set()

KNOWN_MEME_TOKENS = [
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",
    "MEW1gQWJ3nEXg2qgERiKu7FAFj79PHvQVREQUzScPP5",
]

def get_sol_price():
    try:
        url = "https://api.dexscreener.com/tokens/v1/solana/So11111111111111111111111111111111111111112"
        r = requests.get(url, timeout=10)
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            return float(data[0].get("priceUsd", 150))
    except:
        pass
    return 150

def get_trending_tokens():
    try:
        url = "https://api.dexscreener.com/token-boosts/top/v1"
        r = requests.get(url, timeout=10)
        data = r.json()
        tokens = []
        if isinstance(data, list):
            for item in data[:20]:
                if item.get("chainId") == "solana":
                    tokens.append(item.get("tokenAddress"))
        return tokens
    except:
        return KNOWN_MEME_TOKENS

def get_token_info(mint):
    try:
        url = f"https://api.dexscreener.com/tokens/v1/solana/{mint}"
        r = requests.get(url, timeout=10)
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            pair = data[0]
            symbol = pair.get("baseToken", {}).get("symbol", "UNKNOWN")
            price = float(pair.get("priceUsd", 0))
            mcap = pair.get("marketCap", 0)
            return symbol, price, mcap
    except:
        pass
    return "UNKNOWN", 0, 0

def format_mcap(mcap):
    try:
        mcap = float(mcap)
        if mcap >= 1_000_000_000:
            return f"${mcap/1_000_000_000:.2f}B"
        elif mcap >= 1_000_000:
            return f"${mcap/1_000_000:.2f}M"
        elif mcap >= 1_000:
            return f"${mcap/1_000:.2f}K"
        return f"${mcap:.2f}"
    except:
        return "?"

def get_token_traders(mint):
    try:
        url = f"https://api.helius.xyz/v0/addresses/{mint}/transactions?api-key={HELIUS_API_KEY}&limit=50&type=SWAP"
        r = requests.get(url, timeout=10)
        return r.json()
    except:
        return []

def analyze_wallet(wallet, txs, sol_price):
    wins = 0
    losses = 0
    total_profit = 0

    for tx in txs:
        if tx.get("feePayer") != wallet:
            continue
        native = tx.get("nativeTransfers", [])
        sol_in = sum(t.get("amount", 0) for t in native if t.get("toUserAccount") == wallet) / 1e9
        sol_out = sum(t.get("amount", 0) for t in native if t.get("fromUserAccount") == wallet) / 1e9
        pnl = (sol_in - sol_out) * sol_price
        if pnl > 0:
            wins += 1
            total_profit += pnl
        elif pnl < 0:
            losses += 1

    total = wins + losses
    if total < MIN_TRADES:
        return None

    winrate = (wins / total) * 100
    if winrate < MIN_WINRATE:
        return None
    if total_profit < MIN_PROFIT:
        return None

    return {
        "winrate": round(winrate, 1),
        "profit": round(total_profit, 0),
        "wins": wins,
        "losses": losses
    }

def get_latest_swap(wallet):
    try:
        url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions?api-key={HELIUS_API_KEY}&limit=5&type=SWAP"
        r = requests.get(url, timeout=10)
        txs = r.json()
        if txs and isinstance(txs, list):
            return txs[0]
    except:
        pass
    return None

async def scan_whales(app):
    global bot_aktif
    sol_price = get_sol_price()

    while True:
        try:
            if not bot_aktif:
                await asyncio.sleep(30)
                continue

            tokens = get_trending_tokens()
            print(f"Scanning {len(tokens)} trending tokens...")

            for mint in tokens:
                txs = get_token_traders(mint)
                if not txs or not isinstance(txs, list):
                    continue

                wallets_seen = set()
                for tx in txs:
                    wallet = tx.get("feePayer", "")
                    if not wallet or wallet in wallets_seen:
                        continue
                    wallets_seen.add(wallet)

                    stats = analyze_wallet(wallet, txs, sol_price)
                    if not stats:
                        continue

                    latest = get_latest_swap(wallet)
                    if not latest:
                        continue

                    sig = latest.get("signature", "")
                    if sig in notified_tx:
                        continue

                    token_transfers = latest.get("tokenTransfers", [])
                    native_transfers = latest.get("nativeTransfers", [])

                    token_in = None
                    amount_in = 0
                    sol_out = sum(t.get("amount", 0) for t in native_transfers if t.get("fromUserAccount") == wallet) / 1e9
                    sol_in = sum(t.get("amount", 0) for t in native_transfers if t.get("toUserAccount") == wallet) / 1e9

                    for t in token_transfers:
                        if t.get("toUserAccount") == wallet:
                            token_in = t.get("mint")
                            amount_in = t.get("tokenAmount", 0)

                    if sol_out > MIN_SOL_TRADE and token_in:
                        action = "BUY 🚀"
                        emoji = "🟢"
                        sol_amt = round(sol_out, 4)
                        usd_amt = round(sol_out * sol_price, 2)
                    elif sol_in > MIN_SOL_TRADE:
                        action = "SELL 💰"
                        emoji = "🔴"
                        sol_amt = round(sol_in, 4)
                        usd_amt = round(sol_in * sol_price, 2)
                    else:
                        continue

                    token_name, price, mcap = get_token_info(token_in or mint)
                    amount_fmt = f"{float(amount_in):,.0f}" if amount_in else "?"
                    price_fmt = f"${price:.8f}" if price > 0 else "?"
                    mcap_fmt = format_mcap(mcap)
                    wallet_short = f"{wallet[:4]}...{wallet[-4:]}"

                    utc_time = datetime.utcnow()
                    wib_hour = (utc_time.hour + 7) % 24
                    waktu = f"{utc_time.strftime('%H:%M:%S')} UTC ({wib_hour:02d}:{utc_time.strftime('%M')} WIB)"

                    pesan = f"""🐋 *Whale Alert!*
━━━━━━━━━━━━━━━
👤 *Wallet:* `{wallet_short}`
🏆 *Winrate:* {stats['winrate']}%
💰 *Total Profit:* ${stats['profit']:,.0f}
📊 *Trades:* {stats['wins']} win / {stats['losses']} loss
━━━━━━━━━━━━━━━
{emoji} *Action:* {action}
🪙 *Token:* {token_name}
📦 *Amount:* {amount_fmt} {token_name}
💵 *SOL:* {sol_amt} SOL (≈${usd_amt})
💲 *Price:* {price_fmt}
📈 *MCap:* {mcap_fmt}
🕐 *Time:* {waktu}
━━━━━━━━━━━━━━━
🔗 [Solscan](https://solscan.io/tx/{sig}) | 📊 [DexScreener](https://dexscreener.com/solana/{token_in or mint})"""

                    await app.bot.send_message(
                        chat_id=TELEGRAM_CHAT_ID,
                        text=pesan,
                        parse_mode="Markdown"
                    )
                    notified_tx.add(sig)
                    whale_list[wallet] = stats

            await asyncio.sleep(60)

        except Exception as e:
            print(f"Error: {e}")
            await asyncio.sleep(30)

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "✅ Aktif" if bot_aktif else "⛔ Berhenti"
    sol_price = get_sol_price()
    pesan = f"🐋 *Whale Screener*: {status}\n\n"
    pesan += f"💲 *SOL:* ${sol_price:.2f}\n"
    pesan += f"🏆 *Min Winrate:* {MIN_WINRATE}%\n"
    pesan += f"💰 *Min Profit:* ${MIN_PROFIT:,}\n"
    pesan += f"📊 *Min Trades:* {MIN_TRADES}x\n\n"
    pesan += f"🐋 *Whales ditemukan:* {len(whale_list)}"
    await update.message.reply_text(pesan, parse_mode="Markdown")

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_aktif
    bot_aktif = True
    await update.message.reply_text("✅ Whale Screener aktif!")

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_aktif
    bot_aktif = False
    await update.message.reply_text("⛔ Whale Screener berhenti!")

async def main():
    print("Whale Screener Bot")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stop", cmd_stop))
    async with app:
        await app.start()
        await app.updater.start_polling()
        await app.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text="🐋 *Whale Screener AKTIF!*\n\nScan otomatis whale meme Solana!\n\n🏆 Min Winrate: 65%\n💰 Min Profit: $5,000\n📊 Min Trades: 10x\n\n/status /start /stop",
            parse_mode="Markdown"
        )
        await scan_whales(app)
        await app.updater.stop()
        await app.stop()

asyncio.run(main())
