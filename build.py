"""Bouwt site/index.html uit besluiten.json (zie ophalen.py). Stopt met een fout als de data niet klopt."""
import json, sys, collections as C, datetime as dt, html, pathlib

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

data = dict(
    stand=max(r["datum"] for r in rijen), gebouwd=dt.date.today().isoformat(), start=START,
    n_stemmingen=len(rijen), n_omstreden=len(omstreden),
    indeling=dict(coalitie=COALITIE, links=LINKS, rechts=RECHTS, midden=MIDDEN),
    totaal=totaal, per_maand=per_maand, maanden=maanden, gelijk=gelijk, anderen=ANDEREN,
    volgt=volgt, partner=PARTNER, zetels=zetels, met_coalitie=met_coalitie, partner_split=partner_split, n_eensgezind=len(eens),
    splits=splits, split_tel={f: dict(c) for f, c in split_tel.items()},
    blok={s: dict(blok[s]) for s in ["Wet", "Amendement", "Motie", "Alles"]},
    blok_kw={q: dict(c) for q, c in sorted(blok_kw.items())},
)
SITE.mkdir(exist_ok=True)
json.dump(data, open(vorige, "w"), ensure_ascii=False)
pagina = open("template.html").read().replace(
    "/*DATA*/null", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
pagina = pagina.replace("{{STAND}}", html.escape(dt.date.fromisoformat(data["stand"]).strftime("%-d-%-m-%Y")))
open(SITE / "index.html", "w").write(pagina)
print(f"ok: {len(rijen)} stemmingen, {len(omstreden)} omstreden, {len(splits)} met verdeelde coalitie, stand {data['stand']}")
for f in COALITIE:
    print(f"  {f}: met links in {100 * totaal[f]['links'] / totaal[f]['n']:.1f}% van {totaal[f]['n']} omstreden stemmingen; alleen: {dict(split_tel[f])}")
