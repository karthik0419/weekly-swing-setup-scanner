"""
Telegram Notifier — Weekly Swing Setup Scanner
Reads latest weekly results CSV and sends top setups to Telegram.

Usage:
  python telegram_notify.py               # auto-picks latest CSV
  python telegram_notify.py --top 15
  python telegram_notify.py --csv results/weekly_2026-05-18.csv
"""

import os, sys, argparse, glob
import pandas as pd
from datetime import date

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    env = {}
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return env


def send_telegram(token, chat_id, text):
    import requests
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }, timeout=15)
    return resp.ok


def format_message(df, top):
    rows = df.head(top)
    medals = ["🥇", "🥈", "🥉"] + [f"{i+1}⃣" for i in range(3, top)]

    lines = [
        f"<b>📊 WEEKLY SWING SCAN — {date.today().strftime('%d %b %Y')}</b>",
        f"🔍 Scanned: Full NSE EQ (~2000+ stocks) | Found: {len(df)} setups",
        "",
    ]

    for i, (_, row) in enumerate(rows.iterrows()):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        sym   = str(row["symbol"]).replace(".NS", "")
        pat   = str(row["pattern"])
        score = row["score"]
        rr    = row["rr"]
        cmp   = row["cmp"]
        entry = row["breakout"]
        stop  = row["stop_loss"]
        tgt   = row["target"]
        up    = row["upside_%"]

        lines += [
            "━━━━━━━━━━━━━━━━━━━",
            f"{medal} <b>{sym}</b> | Score: {score} | {pat}",
            f"💰 CMP: ₹{cmp}  |  Entry: ₹{entry}",
            f"🛑 Stop: ₹{stop}  |  🎯 Target: ₹{tgt}",
            f"📈 Upside: {up}%  |  RR: {rr}x",
        ]

    lines += [
        "━━━━━━━━━━━━━━━━━━━",
        "",
        "⚠️ For research only. Not financial advice.",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=None)
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args()

    env = load_env()
    token   = env.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = env.get("TELEGRAM_CHAT_ID")   or os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID in .env")
        sys.exit(1)

    # Find latest CSV
    if args.csv:
        csv_path = args.csv
    else:
        results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
        files = sorted(glob.glob(os.path.join(results_dir, "weekly_*.csv")))
        if not files:
            print("No results CSV found. Run scanner.py first.")
            sys.exit(1)
        csv_path = files[-1]

    print(f"Reading: {csv_path}")
    df = pd.read_csv(csv_path).sort_values("score", ascending=False)

    if df.empty:
        print("No results to send.")
        sys.exit(0)

    msg = format_message(df, args.top)
    print("Sending to Telegram...")
    print(msg)

    if send_telegram(token, chat_id, msg):
        print("Sent successfully.")
    else:
        print("Failed to send.")
        sys.exit(1)


if __name__ == "__main__":
    main()
