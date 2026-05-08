import os
import smtplib
import time
import xml.etree.ElementTree as ET
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.parse import quote

RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "sratheeshans@gmail.com")
SENDER_EMAIL    = os.environ.get("SENDER_EMAIL", "")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD", "")
GEO             = os.environ.get("GEO", "US")
TOP_N           = int(os.environ.get("TOP_N", "10"))

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TrendBot/1.0)"}

def fetch_rss(url: str) -> list[str]:
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=15) as r:
            tree = ET.parse(r)
        root = tree.getroot()
        titles = []
        for item in root.findall(".//item"):
            t = item.find("title")
            if t is not None and t.text:
                titles.append(t.text.strip())
        return titles
    except Exception as e:
        print(f"RSS fetch error ({url}): {e}")
        return []

def get_trending(geo: str = "US") -> list[str]:
    url = f"https://trends.google.com/trending/rss?geo={geo}"
    print(f"Fetching: {url}")
    results = fetch_rss(url)
    print(f"Found {len(results)} trends")
    return results[:TOP_N]

def get_related(keyword: str, geo: str = "US") -> list[str]:
    encoded = quote(keyword)
    url = f"https://trends.google.com/trends/trendingsearches/daily/rss?geo={geo}&q={encoded}"
    results = fetch_rss(url)
    related = [r for r in results if r.lower() != keyword.lower()]
    return related[:5]

def build_html(trends: list[str], related_map: dict) -> str:
    date_str = datetime.now().strftime("%A %d %B %Y")
    rows = ""
    for i, term in enumerate(trends, 1):
        related = related_map.get(term, [])
        related_str = " &nbsp;·&nbsp; ".join(related) if related else "—"
        rows += f"""
        <tr style="border-bottom:1px solid #eee;">
          <td style="padding:11px 10px;font-weight:600;color:#111;font-size:14px;">{i}. {term}</td>
          <td style="padding:11px 10px;color:#555;font-size:13px;">{related_str}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:24px;">
  <div style="max-width:660px;margin:0 auto;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,0.08);">
    <div style="background:#0f0f0f;padding:24px 28px;">
      <h1 style="margin:0;color:#fff;font-size:20px;">📈 Trend Report</h1>
      <p style="margin:6px 0 0;color:#aaa;font-size:13px;">{date_str} &nbsp;·&nbsp; Region: {geo_label(GEO)}</p>
    </div>
    <div style="padding:20px 28px;">
      <table style="width:100%;border-collapse:collapse;">
        <thead>
          <tr style="background:#f7f7f7;">
            <th style="padding:10px;text-align:left;color:#333;font-size:13px;border-bottom:2px solid #eee;">Trending now</th>
            <th style="padding:10px;text-align:left;color:#e07000;font-size:13px;border-bottom:2px solid #eee;">Related searches 🔥</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      <p style="margin-top:20px;font-size:11px;color:#bbb;">Source: Google Trends RSS · Automated by trend-agent on GitHub Actions</p>
    </div>
  </div>
</body></html>"""

def geo_label(geo: str) -> str:
    labels = {"US": "United States", "NL": "Netherlands", "GB": "United Kingdom", "AU": "Australia"}
    return labels.get(geo, geo)

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
    trends = get_trending(GEO)
    if not trends:
        print("No trends fetched. Aborting.")
        return

    print(f"Top trends: {trends}")

    related_map = {}
    for term in trends:
        print(f"  Related for: {term}")
        related_map[term] = get_related(term, GEO)
        time.sleep(1)

    html = build_html(trends, related_map)
    subject = f"📈 Trend Report {datetime.now().strftime('%d %b %Y')} — Top {len(trends)} ({GEO})"
    send_email(subject, html)

if __name__ == "__main__":
    run()
