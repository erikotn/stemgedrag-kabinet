"""Maakt PNG's van onderdelen van de pagina, voor een draadje op Bluesky. Gebruik: python3 afbeeldingen.py [url]"""
import sys, pathlib
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "https://stemgedrag-kabinet.pages.dev/"
UIT = pathlib.Path("bluesky")
UIT.mkdir(exist_ok=True)

# (bestandsnaam, selector, js die vóór de screenshot binnen het element opruimt)
KAARTEN = [
    ("1-meerderheden.png", "#kern-blok", ""),
    ("2-kabinet.png", "#conclusie .conclusie:nth-of-type(1)", ""),
    ("3-links-rechts.png", "#splitbars", "kop(el, 'Als links en rechts tegenover elkaar staan: met welke kant stemt de partij mee?')"),
    ("4-afwijken.png", "#splitcount", "kop(el, 'Hoe vaak stemde elke partij anders dan de andere twee coalitiepartijen – en met wie dan?')"),
    ("5-ja21.png", "#conclusie .conclusie:nth-of-type(4)",
     "const h = el.querySelectorAll('h3'); if (h[1]) { let n = h[1]; while (n) { const v = n.nextElementSibling; n.remove(); n = v; } }"),
]

with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome")
    pg = b.new_page(viewport={"width": 720, "height": 1000}, device_scale_factor=2, color_scheme="light")
    pg.goto(URL, wait_until="networkidle")
    stand = pg.evaluate("D.stand.split('-').reverse().join('-')")
    for naam, sel, opruim in KAARTEN:
        el = pg.locator(sel).first
        # kaarten zonder eigen rand: in de omringende .card fotograferen
        el = el.locator("xpath=ancestor-or-self::*[contains(@class,'card') or contains(@class,'conclusie') or contains(@class,'hero')][1]")
        el.evaluate("""(el, [opruim, stand]) => {
            el.querySelectorAll('details').forEach(d => d.remove());
            const kop = (el, t) => { const h = document.createElement('div'); h.style.cssText = 'font-size:20px;font-weight:650;line-height:1.3;margin:0 0 14px;color:#0b0b0b'; h.textContent = t; el.prepend(h); };
            new Function('el', 'kop', opruim)(el, kop);
            const v = document.createElement('div');
            v.style.cssText = 'margin-top:14px;font-size:12px;color:#7a7975';
            v.textContent = 'stemgedrag-kabinet.pages.dev · bron: open data Tweede Kamer · stemmingen t/m ' + stand;
            el.appendChild(v);
        }""", [opruim, stand])
        el.screenshot(path=str(UIT / naam))
        print("gemaakt:", UIT / naam)
    b.close()
