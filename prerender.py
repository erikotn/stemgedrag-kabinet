"""Rendert elke pagina in site/ vooraf in een browser, zodat zoekmachines de volledige tekst zien,
en maakt per pagina een deelafbeelding (Open Graph, 1200x630) in site/og/."""
import json, threading, functools, http.server, pathlib
from playwright.sync_api import sync_playwright

SITE = pathlib.Path("site")
(SITE / "og").mkdir(exist_ok=True)
handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE))
handler.log_message = lambda *a: None
server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
BASIS = f"http://127.0.0.1:{server.server_address[1]}"

with sync_playwright() as p:
    try:
        browser = p.chromium.launch()
    except Exception:
        browser = p.chromium.launch(channel="chrome")   # lokaal: geïnstalleerde Chrome
    page = browser.new_page(viewport={"width": 1200, "height": 630}, device_scale_factor=1, color_scheme="light")
    for item in json.load(open(SITE / "paginas.json")):
        pad = item["pad"]
        page.goto(BASIS + pad, wait_until="networkidle")
        page.wait_for_timeout(150)
        page.screenshot(path=str(SITE / "og" / f"{item['og']}.png"))
        html = page.evaluate("""() => {
            document.querySelectorAll('body > .tip').forEach(e => e.remove());
            return '<!doctype html>\\n' + document.documentElement.outerHTML;
        }""")
        bestand = SITE / (pad.strip("/") + "/index.html" if pad != "/" else "index.html")
        bestand.write_text(html)
        print("vooraf gerenderd:", pad)
    browser.close()
server.shutdown()
