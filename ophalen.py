"""Haalt alle stemmingsbesluiten sinds de beëdiging van kabinet-Jetten op uit het Gegevensmagazijn."""
import json, time, urllib.error, urllib.request, urllib.parse

BASE = "https://gegevensmagazijn.tweedekamer.nl/OData/v4/2.0/Besluit"
params = {
    "$filter": "Verwijderd eq false and startswith(BesluitSoort,'Stemmen') "
               "and Agendapunt/Activiteit/Datum ge 2026-02-23T00:00:00Z",
    "$select": "Id,BesluitSoort,BesluitTekst,StemmingsSoort",
    "$expand": "Agendapunt($select=Id;$expand=Activiteit($select=Datum)),"
               "Zaak($select=Soort,Nummer,Onderwerp,Titel;$expand=Document($select=DocumentNummer,Soort,Datum),ZaakActor($select=ActorNaam,ActorFractie,Relatie)),"
               "Stemming($filter=Verwijderd eq false;$select=ActorFractie,Soort,FractieGrootte,Persoon_Id,Vergissing)",
    "$top": "250",
}
alles, skip = [], 0
while True:
    p = dict(params, **{"$skip": str(skip), "$orderby": "Id"})
    url = BASE + "?" + urllib.parse.urlencode(p, quote_via=urllib.parse.quote)
    for poging in range(5):   # het Gegevensmagazijn geeft af en toe een 500 of time-out; dan even wachten en opnieuw
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                d = json.load(r)
            break
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            if poging == 4:
                raise
            print(f"fout bij skip {skip}: {e}, opnieuw over {30 * (poging + 1)} s", flush=True)
            time.sleep(30 * (poging + 1))
    if not d["value"]:
        break
    alles += d["value"]
    skip += len(d["value"])
    print(len(alles), flush=True)

with open("besluiten.json", "w") as f:
    json.dump(alles, f)
print("klaar:", len(alles))
