"""Шаг 8в. Сборка лендинга в один автономный файл site/index.html (без сервера и внешних запросов)."""
import sys

sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
S = ROOT / "site_src"
html = (S / "index.html").read_text(encoding="utf-8")
parts = {
    "/*STYLES*/": (S / "theme.css").read_text(encoding="utf-8"),
    "/*D3*/": (S / "vendor" / "d3.v7.min.js").read_text(encoding="utf-8"),
    "/*GEO*/": (S / "data" / "geo.json").read_text(encoding="utf-8"),
    # длинное тире в текстах из отчётных таблиц заменяем на дефис (стиль лендинга)
    "/*DATA*/": (S / "data" / "site.json").read_text(encoding="utf-8").replace("</", r"<\/").replace("—", "-").replace("\u2014", "-"),
    "/*APP*/": (S / "app.js").read_text(encoding="utf-8"),
}
import base64

# шрифты заставки (Ruslan Display и Prata, OFL; подмножества нужных букв) и фото автора — внутрь файла
font = base64.b64encode((S / "fonts" / "ruslan-uklad.woff2").read_bytes()).decode()
parts["/*STYLES*/"] = parts["/*STYLES*/"].replace("/*FONT_UKLAD*/", font).replace(
    "/*FONT_PRATA*/", base64.b64encode((S / "fonts" / "prata-intro.woff2").read_bytes()).decode())
photo = next((p for p in [S / "assets" / f"author.{e}" for e in ("jpg", "jpeg", "png", "webp")] if p.exists()), None)
if photo:
    mime = "image/jpeg" if photo.suffix in (".jpg", ".jpeg") else f"image/{photo.suffix[1:]}"
    tag = f'<img class="author-photo" alt="Фото автора" src="data:{mime};base64,{base64.b64encode(photo.read_bytes()).decode()}">'
else:
    tag = '<div class="author-photo ph" aria-hidden="true">У</div>'
html = html.replace("<!--AUTHOR_PHOTO-->", tag, 1)
for k, v in parts.items():
    if k not in html:
        sys.exit(f"нет метки {k} в шаблоне")
    html = html.replace(k, v, 1)
out = ROOT / "site" / "index.html"
out.parent.mkdir(exist_ok=True)
out.write_text(html, encoding="utf-8")
print(f"site/index.html: {len(html.encode('utf-8')) / 1e6:.2f} МБ")

# PDF-версия лендинга (site/uklad.pdf) — печать headless-Chrome; если браузера нет, шаг пропускается
import shutil
import subprocess

chrome = next((c for c in [shutil.which("chrome"), shutil.which("google-chrome"), shutil.which("chromium"),
                           r"C:\Program Files\Google\Chrome\Application\chrome.exe"] if c and Path(c).exists()), None)
if chrome:
    pdf = out.with_name("uklad.pdf")
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--virtual-time-budget=15000",
                    f"--print-to-pdf={pdf}", out.resolve().as_uri()], capture_output=True, timeout=180)
    print(f"site/uklad.pdf: {pdf.stat().st_size / 1e6:.2f} МБ" if pdf.exists() else "PDF не собран")
else:
    print("Chrome не найден — site/uklad.pdf не собран")
