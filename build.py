"""Bouwt site/index.html uit besluiten.json (zie ophalen.py). Stopt met een fout als de data niet klopt."""
import json, sys, collections as C, datetime as dt, html, pathlib
import numpy as np

COALITIE = ["D66", "CDA", "VVD"]
LINKS = ["PRO", "GroenLinks-PvdA", "SP", "PvdD", "DENK", "Volt"]
RECHTS = ["PVV", "Groep Markuszower", "JA21", "FVD", "BBB", "SGP", "Keijzer"]
MIDDEN = ["ChristenUnie", "50PLUS"]
SOORT = {"Motie": "Motie", "Amendement": "Amendement", "Wetgeving": "Wet", "Initiatiefwetgeving": "Wet", "Begroting": "Wet"}
START = "2026-02-23"
SITE = pathlib.Path("site")


def fout(msg):
    sys.exit(f"DATACHECK MISLUKT: {msg}")


def posities(b):
    """Per fractie: zetels voor, zetels tegen. Hoofdelijk telt per persoon."""
    voor, tegen = C.Counter(), C.Counter()
    for s in b["Stemming"]:
        n = 1 if s["Persoon_Id"] else s["FractieGrootte"]
        if s["Soort"] == "Voor":
            voor[s["ActorFractie"]] += n
        elif s["Soort"] == "Tegen":
            tegen[s["ActorFractie"]] += n
    return voor, tegen


def pos(voor, tegen, groep):
    v, t = sum(voor[f] for f in groep), sum(tegen[f] for f in groep)
    return "V" if v > t else "T" if t > v else None


def link(zaak):
    docs = sorted(zaak.get("Document", []), key=lambda d: d.get("Datum") or "", reverse=True)
    for prefix, pad in (("Motie", "moties"), ("Amendement", "amendementen")):
        for d in docs:
            if (d["Soort"] or "").startswith(prefix):
                return f"https://www.tweedekamer.nl/kamerstukken/{pad}/detail?id={zaak['Nummer']}&did={d['DocumentNummer']}"
    return f"https://www.tweedekamer.nl/zoeken?qry={zaak['Nummer']}"


besluiten = json.load(open("besluiten.json"))
bekend = set(COALITIE + LINKS + RECHTS + MIDDEN)
rijen, zetelfout = [], 0
for b in besluiten:
    if not b["Stemming"] or b["BesluitSoort"] not in ("Stemmen - aangenomen", "Stemmen - verworpen"):
        continue
    voor, tegen = posities(b)
    nieuw = (set(voor) | set(tegen)) - bekend
    if nieuw:
        fout(f"onbekende fractie(s) {sorted(nieuw)} – deel ze in bij LINKS/RECHTS/MIDDEN")
    if b["StemmingsSoort"] == "Met handopsteken" and sum(s["FractieGrootte"] for s in b["Stemming"]) != 150:
        zetelfout += 1
    zaak = b["Zaak"][0] if b["Zaak"] else {"Nummer": "", "Onderwerp": ""}
    rijen.append(dict(
        datum=b["Agendapunt"]["Activiteit"]["Datum"][:10],
        soort=SOORT.get(zaak.get("Soort"), "Overig"),
        aangenomen=b["BesluitSoort"].endswith("aangenomen"),
        onderwerp=zaak.get("Onderwerp") or zaak.get("Titel") or "",
        url=link(zaak) if zaak["Nummer"] else "",
        p={f: pos(voor, tegen, [f]) for f in COALITIE},
        alle={f: pos(voor, tegen, [f]) for f in bekend},
        L=pos(voor, tegen, LINKS), R=pos(voor, tegen, RECHTS),
        zk=sum(voor[f] for f in COALITIE), zl=sum(voor[f] for f in LINKS),
        zr=sum(voor[f] for f in RECHTS), zm=sum(voor[f] for f in MIDDEN),
        V=sum(voor.values()), T=sum(tegen.values()), vt=dict(voor), tg=dict(tegen),
        indiener=next((a["ActorFractie"] for a in zaak.get("ZaakActor", []) if a.get("Relatie") == "Indiener"), None),
        nummer=zaak.get("Nummer", ""), zsoort=zaak.get("Soort"),
    ))

# --- datacheck -------------------------------------------------------------
if len(rijen) < 1000:
    fout(f"maar {len(rijen)} stemmingen gevonden")
if zetelfout > 0.02 * len(rijen):
    fout(f"{zetelfout} stemmingen tellen niet op tot 150 zetels")
vorige = SITE / "data.json"
if vorige.exists():
    oud = json.load(open(vorige))["n_stemmingen"]
    if len(rijen) < oud:
        fout(f"minder stemmingen dan vorige keer ({len(rijen)} < {oud})")

# --- 1. omstreden stemmingen: links en rechts staan tegenover elkaar ---------
omstreden = [r for r in rijen if r["L"] and r["R"] and r["L"] != r["R"]]
maanden = sorted({r["datum"][:7] for r in omstreden})
per_maand = {f: [] for f in COALITIE}
totaal = {}
for f in COALITIE:
    met = [r for r in omstreden if r["p"][f]]
    links = sum(r["p"][f] == r["L"] for r in met)
    totaal[f] = dict(links=links, n=len(met))
    for m in maanden:
        mm = [r for r in met if r["datum"].startswith(m)]
        per_maand[f].append(dict(maand=m, links=sum(r["p"][f] == r["L"] for r in mm), n=len(mm)))

# --- 1b. overeenstemming met elke andere fractie (alle stemmingen) ------------
ANDEREN = [f for f in LINKS + MIDDEN + RECHTS]
gelijk = {f: {} for f in COALITIE}
for f in COALITIE:
    for g in ANDEREN:
        beide = [r for r in rijen if r["alle"][f] and r["alle"][g]]
        gelijk[f][g] = dict(zelfde=sum(r["alle"][f] == r["alle"][g] for r in beide), n=len(beide))

# --- 1c. hoe vaak volgt elke fractie het standpunt van haar eigen blok ------------
volgt = {}
for f, blk in [(f, "L") for f in LINKS] + [(f, "R") for f in RECHTS]:
    m = [r for r in rijen if r["alle"][f] and r[blk]]
    if m:
        volgt[f] = round(100 * sum(r["alle"][f] == r[blk] for r in m) / len(m))

# --- 1d. JA21 als mogelijke partner -------------------------------------------
PARTNER = "JA21"
laatste = max((b for b in besluiten if b["StemmingsSoort"] == "Met handopsteken" and b["Stemming"]),
              key=lambda b: b["Agendapunt"]["Activiteit"]["Datum"])
zetels = {s["ActorFractie"]: s["FractieGrootte"] for s in laatste["Stemming"]}
eens = [r for r in rijen if None not in r["p"].values() and len(set(r["p"].values())) == 1]
met_coalitie = []
for g in ANDEREN:
    m = [r for r in eens if r["alle"][g]]
    if m:
        met_coalitie.append(dict(f=g, pct=round(100 * sum(r["alle"][g] == r["p"]["D66"] for r in m) / len(m)), n=len(m)))
met_coalitie.sort(key=lambda x: -x["pct"])
partner_split = {}
for f in COALITIE:
    sp = [r for r in rijen if None not in r["p"].values() and len(set(r["p"].values())) == 2
          and list(r["p"].values()).count(r["p"][f]) == 1 and r["alle"][PARTNER]]
    partner_split[f] = dict(n=len(sp), met=sum(r["alle"][PARTNER] == r["p"][f] for r in sp))

# --- 2. verdeelde coalitie ------------------------------------------------------
splits = []
for r in rijen:
    ps = r["p"]
    if None in ps.values() or len(set(ps.values())) == 1:
        continue
    alleen = next(f for f in COALITIE if list(ps.values()).count(ps[f]) == 1)
    kant = lambda x: "links" if x == r["L"] and x != r["R"] else "rechts" if x == r["R"] and x != r["L"] else "–"
    splits.append(dict(datum=r["datum"], soort=r["soort"], onderwerp=r["onderwerp"], url=r["url"],
                       aangenomen=r["aangenomen"], alleen=alleen, alleen_kant=kant(ps[alleen]),
                       stem={f: ps[f] for f in COALITIE}))
splits.sort(key=lambda s: s["datum"], reverse=True)
split_tel = {f: C.Counter(s["alleen_kant"] for s in splits if s["alleen"] == f) for f in COALITIE}

# --- 3. waar vindt de eensgezinde coalitie haar meerderheid ---------------------
CATS = ["breed", "links", "rechts", "overig"]
blok = C.defaultdict(C.Counter)
blok_kw = C.defaultdict(C.Counter)
for r in rijen:
    if not all(v == "V" for v in r["p"].values()):
        continue
    k, l, rr, m = r["zk"], r["zl"], r["zr"], r["zm"]
    cat = "breed" if k + l >= 76 and k + rr >= 76 else "links" if k + l >= 76 else "rechts" if k + rr >= 76 else "overig"
    blok[r["soort"]][cat] += 1
    blok["Alles"][cat] += 1
    blok_kw[f"{r['datum'][:4]} K{(int(r['datum'][5:7]) - 1) // 3 + 1}"][cat] += 1

kab = dict(
    stand=max(r["datum"] for r in rijen), gebouwd=dt.date.today().isoformat(), start=START,
    n_stemmingen=len(rijen), n_omstreden=len(omstreden),
    indeling=dict(coalitie=COALITIE, links=LINKS, rechts=RECHTS, midden=MIDDEN),
    totaal=totaal, per_maand=per_maand, maanden=maanden, gelijk=gelijk, anderen=ANDEREN,
    volgt=volgt, partner=PARTNER, zetels=zetels, met_coalitie=met_coalitie, partner_split=partner_split, n_eensgezind=len(eens),
    splits=splits, split_tel={f: dict(c) for f, c in split_tel.items()},
    blok={s: dict(blok[s]) for s in ["Wet", "Amendement", "Motie", "Alles"]},
    blok_kw={q: dict(c) for q, c in sorted(blok_kw.items())},
)

# --- 4. wie gaf de doorslag ------------------------------------------------------
HUIDIG = sorted((f for f in zetels if zetels[f] > 0), key=lambda f: (-zetels[f], f.lower()))
BLOK = {**{f: "links" for f in LINKS}, **{f: "rechts" for f in RECHTS}, **{f: "midden" for f in MIDDEN}, **{f: "coalitie" for f in COALITIE}}
mismatch = 0
for r in rijen:
    uit = r["V"] > r["T"]
    r["marge"] = abs(r["V"] - r["T"])
    def omgedraaid(f):
        V = r["V"] - r["vt"].get(f, 0) + r["tg"].get(f, 0); T = r["T"] - r["tg"].get(f, 0) + r["vt"].get(f, 0)
        return T > V if uit else V > T          # echt andersom, niet alleen gelijke stand
    r["doorslag"] = sorted(f for f in set(r["vt"]) | set(r["tg"]) if omgedraaid(f))
    mismatch += uit != r["aangenomen"]
if mismatch > 0.01 * len(rijen):
    fout(f"{mismatch} stemmingen waarvan de zetels niet kloppen met de uitslag")
doorslag_n = C.Counter(f for r in rijen for f in r["doorslag"])
n_krap = sum(1 for r in rijen if r["doorslag"])

# --- 5. laatste stemronde ----------------------------------------------------------
dagen = sorted({r["datum"] for r in rijen})
ronde_dag = dagen[-1]
def kort(r):
    return dict(soort=r["soort"], onderwerp=r["onderwerp"], url=r["url"], aangenomen=r["aangenomen"],
                V=r["V"], T=r["T"], marge=r["marge"], indiener=r["indiener"], doorslag=r["doorslag"],
                voor=sorted((f for f in HUIDIG if r["alle"].get(f) == "V"), key=lambda f: -zetels[f]))
ronde = [kort(r) for r in rijen if r["datum"] == ronde_dag]
ronde.sort(key=lambda x: x["marge"])
rondes = [dict(datum=d, n=sum(r["datum"] == d for r in rijen), aangenomen=sum(r["datum"] == d and r["aangenomen"] for r in rijen)) for d in dagen[-12:]]

# --- 6. politiek landschap (wie stemt met wie) -------------------------------------
omstr_alle = [r for r in rijen if len({r["alle"].get(f) for f in HUIDIG} - {None}) == 2]
n = len(HUIDIG)
A = np.ones((n, n))
for i, f in enumerate(HUIDIG):
    for j, g in enumerate(HUIDIG):
        if i < j:
            m = [r for r in omstr_alle if r["alle"].get(f) and r["alle"].get(g)]
            A[i, j] = A[j, i] = sum(r["alle"][f] == r["alle"][g] for r in m) / max(1, len(m))
D2 = (1 - A) ** 2
J = np.eye(n) - 1 / n
Bm = -0.5 * J @ D2 @ J
w, v = np.linalg.eigh(Bm)
idx = np.argsort(w)[::-1][:2]
xy = v[:, idx] * np.sqrt(np.maximum(w[idx], 0))
if "PRO" in HUIDIG and "PVV" in HUIDIG and xy[HUIDIG.index("PRO"), 0] > xy[HUIDIG.index("PVV"), 0]:
    xy[:, 0] *= -1
if "D66" in HUIDIG and xy[HUIDIG.index("D66"), 1] < 0:
    xy[:, 1] *= -1
verklaard = round(100 * float(w[idx].sum() / w[w > 0].sum()))
landschap = [dict(f=f, x=round(float(xy[i, 0]), 4), y=round(float(xy[i, 1]), 4), zetels=zetels[f], blok=BLOK.get(f, "midden")) for i, f in enumerate(HUIDIG)]

# --- 7. per partij ------------------------------------------------------------------
def slug(f):
    return "".join(c if c.isalnum() else "-" for c in f.lower()).strip("-")
partijen = {}
for i, f in enumerate(HUIDIG):
    mee = [r for r in rijen if r["alle"].get(f)]
    won = sum((r["alle"][f] == "V") == r["aangenomen"] for r in mee)
    moties = [r for r in rijen if r["soort"] == "Motie" and r["indiener"] == f]
    partijen[f] = dict(
        f=f, slug=slug(f), zetels=zetels[f], blok=BLOK.get(f, "midden"),
        n=len(mee), won=won, doorslag=doorslag_n.get(f, 0),
        moties=len(moties), moties_aangenomen=sum(r["aangenomen"] for r in moties),
        gelijk={g: round(100 * float(A[i, j])) for j, g in enumerate(HUIDIG) if g != f},
    )

# --- 8a. wiens voorstellen halen het (per kamp van de indiener) -----------------
def kwart(d): return f"{d[:4]} K{(int(d[5:7]) - 1) // 3 + 1}"
succes, succes_kw, succes_ronde, succes_soort = C.defaultdict(lambda: [0, 0]), C.defaultdict(lambda: C.defaultdict(lambda: [0, 0])), C.defaultdict(lambda: [0, 0]), C.defaultdict(lambda: C.defaultdict(lambda: [0, 0]))
for r in rijen:
    k = BLOK.get(r["indiener"])
    if not k:
        continue
    for bak in (succes[k], succes_kw[kwart(r["datum"])][k], succes_soort[r["soort"]][k]) + ((succes_ronde[k],) if r["datum"] == ronde_dag else ()):
        bak[0] += r["aangenomen"]; bak[1] += 1
KAMPEN = ["coalitie", "midden", "links", "rechts"]
succes_d = dict(
    totaal={k: dict(aan=succes[k][0], n=succes[k][1]) for k in KAMPEN},
    kwartaal=[dict(q=q, **{k: round(100 * v[k][0] / v[k][1]) if v[k][1] else None for k in KAMPEN}) for q, v in sorted(succes_kw.items())],
    soort={s: {k: dict(aan=succes_soort[s][k][0], n=succes_soort[s][k][1]) for k in KAMPEN} for s in ["Motie", "Amendement"]},
    ronde={k: dict(aan=succes_ronde[k][0], n=succes_ronde[k][1]) for k in KAMPEN},
)

# --- 8. wint links of rechts, bondjes, afwijkers -----------------------------------
winnaar = lambda r: "links" if (r["L"] == "V") == r["aangenomen"] else "rechts"
bots = [r for r in rijen if r["L"] and r["R"] and r["L"] != r["R"]]
bots_tot = C.Counter(winnaar(r) for r in bots)
bots_maand = C.defaultdict(C.Counter)
for r in bots:
    bots_maand[r["datum"][:7]][winnaar(r)] += 1
bots_soort = {s: dict(C.Counter(winnaar(r) for r in bots if r["soort"] == s)) for s in ["Wet", "Amendement", "Motie"]}
bots_ronde = C.Counter(winnaar(r) for r in bots if r["datum"] == ronde_dag)
doorslag_bots = C.Counter(f for r in bots for f in r["doorslag"])

paren = []
for i, f in enumerate(HUIDIG):
    for j, h in enumerate(HUIDIG):
        if i < j:
            paren.append(dict(a=f, b=h, pct=round(100 * float(A[i, j])), zelfde=BLOK.get(f) == BLOK.get(h)))
binnen_coalitie = [p for p in paren if p["a"] in COALITIE and p["b"] in COALITIE]
onverwacht = sorted((p for p in paren if not p["zelfde"]), key=lambda p: -p["pct"])[:5]
breuken = sorted((p for p in paren if p["zelfde"]), key=lambda p: p["pct"])[:5]

kamp = C.defaultdict(list)
for f in HUIDIG:
    kamp[BLOK.get(f, "midden")].append(f)
def kampstand(r, f):
    """Standpunt van de rest van f's kamp (zetelmeerderheid, zonder f zelf)."""
    rest = [x for x in kamp[BLOK.get(f)] if x != f]
    if BLOK.get(f) == "coalitie":   # coalitie: alleen als de andere twee hetzelfde stemden
        st = {r["alle"].get(x) for x in rest}
        return st.pop() if len(st) == 1 and None not in st else None
    v = sum(zetels[x] for x in rest if r["alle"].get(x) == "V"); t = sum(zetels[x] for x in rest if r["alle"].get(x) == "T")
    return "V" if v > t else "T" if t > v else None
afwijken, overlopers = [], []
for f in HUIDIG:
    if BLOK.get(f) == "midden" or len(kamp[BLOK.get(f)]) < 2:
        continue
    n = a = 0
    for r in rijen:
        st = kampstand(r, f)
        if not r["alle"].get(f) or not st:
            continue
        n += 1
        if r["alle"][f] != st:
            a += 1
            if f in r["doorslag"]:
                overlopers.append(dict(datum=r["datum"], f=f, kamp=BLOK.get(f), onderwerp=r["onderwerp"], url=r["url"], soort=r["soort"],
                                       aangenomen=r["aangenomen"], V=r["V"], T=r["T"], stem=r["alle"][f]))
    afwijken.append(dict(f=f, blok=BLOK.get(f), pct=round(100 * a / max(1, n)), n=n))
afwijken.sort(key=lambda x: -x["pct"])
tegen_eigen = [dict(datum=r["datum"], onderwerp=r["onderwerp"], url=r["url"], V=r["V"], T=r["T"], aangenomen=r["aangenomen"],
                    tegen=[f for f in COALITIE if r["alle"].get(f) == "T"])
               for r in rijen if r["zsoort"] in ("Wetgeving", "Begroting") and any(r["alle"].get(f) == "T" for f in COALITIE)]
tegen_eigen.sort(key=lambda x: x["datum"], reverse=True)
overlopers.sort(key=lambda x: x["datum"], reverse=True)

# --- 9. extra per partij -------------------------------------------------------------
AFW = {x["f"]: x for x in afwijken}
for f, p in partijen.items():
    eigen = [r for r in rijen if r["indiener"] == f]
    groep = [g for g in HUIDIG if BLOK.get(g) == BLOK.get(f)]
    groep_eigen = [r for r in rijen if r["indiener"] in groep]
    p.update(
        groep=BLOK.get(f), groepsleden=groep,
        voorstellen=len(eigen), voorstellen_aan=sum(r["aangenomen"] for r in eigen),
        groep_voorstellen=len(groep_eigen), groep_voorstellen_aan=sum(r["aangenomen"] for r in groep_eigen),
        recent=[dict(datum=r["datum"], onderwerp=r["onderwerp"], url=r["url"], soort=r["soort"], aangenomen=r["aangenomen"], V=r["V"], T=r["T"])
                for r in sorted(eigen, key=lambda r: r["datum"], reverse=True)[:3]],
        afwijken=AFW.get(f, {}).get("pct"),
        overlopers=[o for o in overlopers if o["f"] == f][:3],
        tegen_eigen=[t for t in tegen_eigen if f in t["tegen"]],
    )

home = dict(
    stand=kab["stand"], gebouwd=kab["gebouwd"], start=START, n_stemmingen=len(rijen),
    ronde_dag=ronde_dag, ronde=ronde, rondes=rondes,
    doorslag=[dict(f=f, n=doorslag_n.get(f, 0), zetels=zetels[f], blok=BLOK.get(f, "midden"), slug=slug(f)) for f in HUIDIG],
    n_krap=n_krap, landschap=landschap, verklaard=verklaard, n_omstr_alle=len(omstr_alle),
    partijen=[dict(f=p["f"], slug=p["slug"], zetels=p["zetels"], blok=p["blok"], won=round(100 * p["won"] / max(1, p["n"])), doorslag=p["doorslag"]) for p in partijen.values()],
    kabinet=dict(links=kab["blok"]["Alles"].get("links", 0), rechts=kab["blok"]["Alles"].get("rechts", 0),
                 breed=kab["blok"]["Alles"].get("breed", 0), totaal=sum(kab["blok"]["Alles"].values())),
    indeling=kab["indeling"],
    bots=dict(n=len(bots), links=bots_tot["links"], rechts=bots_tot["rechts"],
              maand=[dict(maand=m, links=c["links"], rechts=c["rechts"]) for m, c in sorted(bots_maand.items())],
              soort=bots_soort, ronde=dict(links=bots_ronde["links"], rechts=bots_ronde["rechts"]),
              doorslag=[dict(f=f, n=doorslag_bots.get(f, 0)) for f in sorted(HUIDIG, key=lambda f: -doorslag_bots.get(f, 0))]),
    onverwacht=onverwacht, breuken=breuken, binnen_coalitie=binnen_coalitie, afwijken=afwijken, succes=succes_d,
    tegen_eigen=tegen_eigen, overlopers=overlopers[:12], overlopers_ronde=[o for o in overlopers if o["datum"] == ronde_dag],
)

# --- schrijven ----------------------------------------------------------------------
BASIS = "https://stemgedrag-kabinet.pages.dev"   # wordt https://dekamerstemt.nl zodra het domein gekoppeld is
STAND_NL = dt.date.fromisoformat(kab["stand"]).strftime("%-d-%-m-%Y")
KLEUR = {"D66": "var(--d66)", "CDA": "var(--cda)", "VVD": "var(--vvd)"}
NAV = open("nav.html").read().replace("{{PARTIJEN}}", '<span class="lbl">Kies een partij:</span>' + "".join(
    f'<a href="/partij/{p["slug"]}/"><span class="dot" style="background:{KLEUR.get(f, {"links": "var(--links)", "rechts": "var(--rechts)"}.get(p["blok"], "var(--midden)"))}"></span>{html.escape(f)}</a>'
    for f, p in partijen.items()))
pagina_lijst = []

def schrijf(sjabloon, data, pad, titel, beschrijving, og, extra_ld=None):
    url = BASIS + pad
    ld = [{"@context": "https://schema.org", "@type": "WebPage", "name": titel, "description": beschrijving, "url": url,
           "inLanguage": "nl", "dateModified": kab["stand"], "isPartOf": {"@type": "WebSite", "name": "De Kamer stemt", "url": BASIS + "/"}}]
    ld += extra_ld or []
    kop = f"""<title>{html.escape(titel)}</title>
<meta name="description" content="{html.escape(beschrijving)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website"><meta property="og:locale" content="nl_NL"><meta property="og:site_name" content="De Kamer stemt">
<meta property="og:title" content="{html.escape(titel)}"><meta property="og:description" content="{html.escape(beschrijving)}">
<meta property="og:url" content="{url}"><meta property="og:image" content="{BASIS}/og/{og}.png">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Literata:ital,opsz,wght@0,7..72,400..700;1,7..72,400..700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="/stijl.css">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>"""
    t = open(sjabloon).read()
    t = t.replace("{{HEAD}}", kop).replace("{{NAV}}", NAV).replace("{{STAND}}", html.escape(STAND_NL))
    t = t.replace("</footer>", '<p class="hoekje">Een hoekje van <a href="https://erikmeijerink.nl">erikmeijerink.nl</a></p></footer>', 1)
    t = t.replace("/*DATA*/null", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    doel = SITE / pad.strip("/") / "index.html" if pad != "/" else SITE / "index.html"
    doel.parent.mkdir(parents=True, exist_ok=True)
    doel.write_text(t)
    pagina_lijst.append(dict(pad=pad, og=og))

SITE.mkdir(exist_ok=True)
json.dump(dict(home, kabinet_data=kab), open(vorige, "w"), ensure_ascii=False)
(SITE / "stijl.css").write_text(open("stijl.css").read())

dataset = {"@context": "https://schema.org", "@type": "Dataset", "name": "Stemgedrag Tweede Kamer sinds 23 februari 2026",
           "description": "Alle stemmingen in de Tweede Kamer sinds de beëdiging van het kabinet-Jetten, per fractie, met afgeleide maten: wie gaf de doorslag, wie stemt met wie, en waar het kabinet zijn meerderheid vindt.",
           "url": BASIS + "/", "inLanguage": "nl", "dateModified": kab["stand"], "temporalCoverage": f"{START}/{kab['stand']}",
           "isBasedOn": "https://opendata.tweedekamer.nl/", "creator": {"@type": "Organization", "name": "De Kamer stemt"},
           "distribution": {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": BASIS + "/data.json"}}
schrijf("home.html", home, "/", "De Kamer stemt – wint links of rechts in de Tweede Kamer?",
        f"Wint links of rechts in de Tweede Kamer? Wie heeft de doorslag, welke bondjes zijn er en wie stemt anders dan verwacht? Alle {len(rijen):,} stemmingen sinds 23 februari 2026, per partij.".replace(",", "."),
        "home", [dataset])
schrijf("kabinet.html", kab, "/kabinet/", "Met wie stemt het kabinet-Jetten? Stemgedrag van D66, CDA en VVD",
        "Zoekt het minderheidskabinet zijn meerderheid links of rechts? Hoe vaak stemmen D66, CDA en VVD met links, met rechts en met JA21? Op basis van alle stemmingen sinds 23 februari 2026.",
        "kabinet")
schrijf("werkwijze.html", dict(indeling=kab["indeling"]), "/werkwijze/", "Werkwijze – De Kamer stemt",
        "Hoe De Kamer stemt de stemmingen van de Tweede Kamer analyseert: bron, kampen, botsingen, doorslag, bondjes en afwijkers.", "home")
for f, p in partijen.items():
    schrijf("partij.html", dict(p=p, home=dict(stand=kab["stand"], partijen=home["partijen"], indeling=kab["indeling"], n_stemmingen=len(rijen))),
            f"/partij/{p['slug']}/", f"Stemgedrag {f} in de Tweede Kamer – met wie stemt {f}?",
            f"Hoe stemt {f} ({p['zetels']} {'zetel' if p['zetels'] == 1 else 'zetels'}) in de Tweede Kamer? Met welke partijen {f} het vaakst hetzelfde stemt, hoe vaak {f} aan de winnende kant stond en de doorslag gaf. Sinds 23 februari 2026.",
            p["slug"])

(SITE / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
    "".join(f"  <url><loc>{BASIS}{x['pad']}</loc><lastmod>{kab['stand']}</lastmod></url>\n" for x in pagina_lijst) + "</urlset>\n")
(SITE / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {BASIS}/sitemap.xml\n")
json.dump(pagina_lijst, open(SITE / "paginas.json", "w"))

print(f"ok: {len(rijen)} stemmingen, {len(omstreden)} omstreden, {len(splits)} met verdeelde coalitie, stand {kab['stand']}, {len(pagina_lijst)} pagina's")
print(f"  laatste ronde {ronde_dag}: {len(ronde)} stemmingen; krappe stemmingen (iemand gaf doorslag): {n_krap}; landschap verklaart {verklaard}%")
print("  doorslag:", ", ".join(f"{f} {doorslag_n.get(f,0)}" for f in HUIDIG))
