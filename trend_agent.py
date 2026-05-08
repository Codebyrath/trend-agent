import os
import smtplib
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from pytrends.request import TrendReq
import time

# ── CONFIG ────────────────────────────────────────────────────────────────────
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "sratheeshans@gmail.com")
SENDER_EMAIL    = os.environ.get("SENDER_EMAIL", "")        # your Gmail address
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD", "")     # Gmail app password
GEO             = os.environ.get("GEO", "US")               # US, NL, GB, etc.
CATEGORY        = int(os.environ.get("CATEGORY", "0"))      # 0=all, 18=shopping
TOP_N           = int(os.environ.get("TOP_N", "10"))
TIMEFRAME       = os.environ.get("TIMEFRAME", "now 7-d")    # now 1-d or now 7-d

# ── PYTRENDS SETUP ────────────────────────────────────────────────────────────
pytrends = TrendReq(hl="en-US", tz=60, timeout=(10, 25))

def get_trending_searches(geo: str = "united_states") -> list[str]:
    """Daily trending searches (real-time)."""
    try:
        df = pytrends.trending_searches(pn=geo)
        return df[0].tolist()[:TOP_N]
    except Exception as e:
        print(f"trending_searches error: {e}")
        return []

def get_realtime_trends(geo: str = "US") -> list[dict]:
    """Real-time trending searches with titles."""
    try:
        df = pytrends.realtime_trending_searches(pn=geo)
        results = []
        for _, row in df.head(TOP_N).iterrows():
            results.append({
                "title": row.get("title", ""),
                "entityNames": row.get("entityNames", []),
            })
        return results
    except Exception as e:
        print(f"realtime_trends error: {e}")
        return []

def get_related_queries(keyword: str) -> dict:
    """For a single keyword: top + rising related queries."""
    try:
        pytrends.build_payload([keyword], timeframe=TIMEFRAME, geo=GEO, cat=CATEGORY)
        time.sleep(1)
        related = pytrends.related_queries()
        top_df    = related.get(keyword, {}).get("top")
        rising_df = related.get(keyword, {}).get("rising")
        top    = top_df["query"].head(5).tolist()    if top_df    is not None else []
        rising = rising_df["query"].head(5).tolist() if rising_df is not None else []
        return {"top": top, "rising": rising}
    except Exception as e:
        print(f"related_queries error for '{keyword}': {e}")
        return {"top": [], "rising": []}

def get_interest_over_time(keywords: list[str]) -> dict:
    """7-day average interest score per keyword (0-100)."""
    try:
        pytrends.build_payload(keywords[:5], timeframe=TIMEFRAME, geo=GEO, cat=CATEGORY)
        df = pytrends.interest_over_time()
        if df.empty:
            return {}
        return {kw: round(df[kw].mean(), 1) for kw in keywords[:5] if kw in df.columns}
    except Exception as e:
        print(f"interest_over_time error: {e}")
        return {}

def build_html_email(trends: list[str], related_map: dict, scores: dict) -> str:
    date_str = datetime.now().strftime("%A %d %B %Y")
    rows = ""
    for i, term in enumerate(trends, 1):
        rel = related_map.get(term, {"top": [], "rising": []})
        score = scores.get(term, "–")
        top_terms    = ", ".join(rel["top"][:3])    or "–"
        rising_terms = ", ".join(rel["rising"][:3]) or "–"
        rows += f"""
        <tr style="border-bottom:1px solid #eee;">
          <td style="padding:10px 8px;font-weight:600;color:#111;">{i}. {term}</td>
          <td style="padding:10px 8px;text-align:center;color:#555;">{score}</td>
          <td style="padding:10px 8px;color:#444;font-size:13px;">{top_terms}</td>
          <td style="padding:10px 8px;color:#e07000;font-size:13px;">{rising_terms}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Trend Report</title></head>
<body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px;">
  <div style="max-width:680px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
    <div style="background:#111;padding:24px 28px;">
      <h1 style="margin:0;color:#fff;font-size:20px;">📈 Commercial Trend Report</h1>
      <p style="margin:6px 0 0;color:#aaa;font-size:13px;">{date_str} · Region: {GEO} · Timeframe: {TIMEFRAME}</p>
    </div>
    <div style="padding:24px 28px;">
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <thead>
          <tr style="background:#f0f0f0;">
            <th style="padding:10px 8px;text-align:left;color:#333;">Trend</th>
            <th style="padding:10px 8px;text-align:center;color:#333;">Score</th>
            <th style="padding:10px 8px;text-align:left;color:#333;">Related (top)</th>
            <th style="padding:10px 8px;text-align:left;color:#e07000;">Rising 🔥</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      <p style="margin-top:24px;font-size:12px;color:#999;">
        Score = avg interest (0–100) over selected timeframe. Rising = breakout queries gaining momentum.<br>
        Category filter: {"Shopping (cat=18)" if CATEGORY == 18 else "All categories"}
      </p>
    </div>
  </div>
</body></html>"""

def send_email(subject: str, html_body: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = RECIPIENT_EMAIL
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
    print(f"Email sent to {RECIPIENT_EMAIL}")

def run():
    print("Fetching trending searches...")
    trends = get_trending_searches(geo=GEO.lower().replace("-", "_")
                                       .replace("us", "united_states")
                                       .replace("nl", "netherlands")
                                       .replace("gb", "united_kingdom"))
    if not trends:
        print("No trends found, aborting.")
        return

    print(f"Top {len(trends)} trends: {trends[:5]}...")

    related_map = {}
    scores = {}
    for i, term in enumerate(trends):
        print(f"  [{i+1}/{len(trends)}] Getting related queries for: {term}")
        related_map[term] = get_related_queries(term)
        time.sleep(2)

    # Batch interest scores (max 5 at a time)
    for i in range(0, len(trends), 5):
        batch = trends[i:i+5]
        batch_scores = get_interest_over_time(batch)
        scores.update(batch_scores)
        time.sleep(2)

    html = build_html_email(trends, related_map, scores)

    subject = f"📈 Trend Report {datetime.now().strftime('%d %b %Y')} — Top {len(trends)} Commercial Trends ({GEO})"
    send_email(subject, html)

if __name__ == "__main__":
    run()
