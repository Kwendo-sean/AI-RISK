"""Generate the booth QR codes and a printable A4 card.

Two QR codes, because one is not enough on a private network:

  1. A Wi-Fi join code (WIFI:...). Android and iOS both read this and offer to join
     the network directly - no typing the password.
  2. The site URL. This only resolves once the phone is on the Pi's network, which is
     exactly why the card walks people through it in order.

Usage:
    python scripts/make_booth_qr.py
    python scripts/make_booth_qr.py --url http://10.42.0.1:8000 --ssid TREPLEX-AIOT \
        --password TreplexAIOT2026 --title "Will AI Take My Job?" --out booth/
"""
from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://10.42.0.1:8000", help="site URL the QR points at")
    parser.add_argument("--ssid", default="TREPLEX-AIOT", help="Wi-Fi network name")
    parser.add_argument("--password", default="TreplexAIOT2026", help="Wi-Fi password")
    parser.add_argument("--security", default="WPA", choices=["WPA", "WEP", "nopass"], help="Wi-Fi security type")
    parser.add_argument("--title", default="Will AI Take My Job?", help="headline on the card")
    parser.add_argument("--out", default="booth", type=Path, help="output directory")
    args = parser.parse_args()

    try:
        import segno
    except ImportError:
        print("segno is required:  pip install segno", file=sys.stderr)
        return 1

    args.out.mkdir(parents=True, exist_ok=True)

    # Escape the WIFI: payload per the de-facto spec - \ ; , : " are special.
    def wifi_escape(value: str) -> str:
        for char in ("\\", ";", ",", ":", '"'):
            value = value.replace(char, "\\" + char)
        return value

    wifi_payload = f"WIFI:T:{args.security};S:{wifi_escape(args.ssid)};P:{wifi_escape(args.password)};;"

    wifi_qr = segno.make(wifi_payload, error="h")
    site_qr = segno.make(args.url, error="h")
    wifi_qr.save(args.out / "qr-wifi.png", scale=10, border=2)
    site_qr.save(args.out / "qr-site.png", scale=10, border=2)
    wifi_svg = wifi_qr.svg_inline(scale=8, border=2)
    site_svg = site_qr.svg_inline(scale=8, border=2)

    card = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Booth card</title>
<style>
  @page {{ size: A4; margin: 14mm; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family: -apple-system, "Segoe UI", Roboto, sans-serif; color:#111; background:#fff; }}
  .card {{ width:182mm; margin:0 auto; text-align:center; }}
  h1 {{ font-size:34pt; line-height:1.02; margin:0 0 4mm; letter-spacing:-.02em; }}
  h1 em {{ color:#c0271f; font-style:normal; }}
  .sub {{ font-size:12pt; color:#555; margin:0 0 9mm; }}
  .steps {{ display:flex; gap:6mm; align-items:stretch; justify-content:center; }}
  .step {{ flex:1; border:1.5pt solid #111; padding:6mm 4mm; }}
  .n {{ display:inline-block; width:9mm; height:9mm; line-height:9mm; border-radius:50%;
        background:#c0271f; color:#fff; font-weight:800; font-size:12pt; margin-bottom:3mm; }}
  .step h2 {{ font-size:13pt; margin:0 0 3mm; }}
  .step svg {{ width:46mm; height:46mm; }}
  .mono {{ font-family: ui-monospace, Consolas, monospace; font-size:13pt; font-weight:700; word-break:break-all; }}
  .note {{ margin-top:9mm; font-size:10pt; color:#444; border-top:1pt solid #ddd; padding-top:4mm; }}
  .note strong {{ color:#111; }}
</style></head>
<body><div class="card">
  <h1>{html.escape(args.title)}</h1>
  <p class="sub">A 2-minute scan of your job. Runs entirely on the Raspberry Pi in front of you.</p>
  <div class="steps">
    <div class="step">
      <span class="n">1</span><h2>Scan to join the Wi-Fi</h2>
      {wifi_svg}
      <p class="mono">{html.escape(args.ssid)}</p>
    </div>
    <div class="step">
      <span class="n">2</span><h2>Then scan to open</h2>
      {site_svg}
      <p class="mono">{html.escape(args.url)}</p>
    </div>
    <div class="step">
      <span class="n">3</span><h2>Or type it in</h2>
      <p style="margin-top:14mm">Join <span class="mono">{html.escape(args.ssid)}</span></p>
      <p>password<br><span class="mono">{html.escape(args.password)}</span></p>
      <p>then open<br><span class="mono">{html.escape(args.url)}</span></p>
    </div>
  </div>
  <p class="note"><strong>No internet needed.</strong> Nothing leaves this device: your answers are
  scored on the Pi, and the AI answering you is a model running on the Pi itself.</p>
</div></body></html>"""

    (args.out / "booth-card.html").write_text(card, encoding="utf-8")
    print(f"wrote {args.out / 'qr-wifi.png'}")
    print(f"wrote {args.out / 'qr-site.png'}")
    print(f"wrote {args.out / 'booth-card.html'}   <- open in a browser, print to A4/PDF")
    print(f"\nWi-Fi payload : {wifi_payload}")
    print(f"Site URL      : {args.url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
