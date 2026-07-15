# ⚽ Sport-Radar 🎾

Ein selbst gehostetes Analyse-Dashboard: zeigt **alle Spiele der nächsten 3 Tage** mit
Formkurven, Tabellenplätzen, Modell-Vorhersagen (Poisson), Quoten-Vergleich und
Tennis-Einschätzungen — **täglich automatisch aktualisiert, komplett kostenlos**.

## Abgedeckte Wettbewerbe

| Fußball | Tennis |
|---|---|
| 1. Bundesliga, 2. Bundesliga, 3. Liga | ATP Tour |
| Serie A, Premier League | WTA Tour |
| La Liga, La Liga 2 (Segunda División) | |

## Wie es funktioniert

```
scripts/fetch_data.py   holt Spielpläne, Ergebnisse, Quoten, Rankings  ->  data/data.json
scripts/build_site.py   rendert daraus das Dashboard                  ->  docs/index.html
.github/workflows/update.yml   führt beides täglich um ~06:00 Uhr aus und pusht das Ergebnis
```

GitHub Pages liefert `docs/index.html` als öffentliche Website aus — der Link ist mit
Freunden teilbar.

**Datenquellen (alle gratis):** OpenLigaDB (1.–3. Bundesliga), ESPN (PL, Serie A, La Liga 1+2,
Tennis-Matches & Weltranglisten), football-data.co.uk (Quoten + Ergebnis-Historie),
TheSportsDB (Tennis-Ergänzung). Keine API-Keys nötig.

**Optional:** Ein kostenloser API-Key von [The Odds API](https://the-odds-api.com)
(500 Credits/Monat) ergänzt Quoten für die 3. Liga und Tennis. Dazu im Repo unter
*Settings → Secrets and variables → Actions* ein Secret `ODDS_API_KEY` anlegen — mehr nicht.

## Einrichtung (einmalig, ~5 Minuten)

1. Neues **öffentliches** GitHub-Repository anlegen (z. B. `sport-radar`) und diese Dateien pushen.
2. **Settings → Pages**: Source = *Deploy from a branch*, Branch = `main`, Ordner = `/docs`.
3. **Actions-Tab**: Workflow „Tägliches Daten-Update“ einmal manuell starten (*Run workflow*).
4. Fertig — die Seite liegt unter `https://<username>.github.io/<repo>/` und aktualisiert
   sich jeden Morgen selbst.

## Vorhersage-Modell (Kurzfassung)

- **Fußball:** Poisson-Modell. Angriffs-/Abwehrstärke je Team aus den Ergebnissen der letzten
  zwei Saisons, exponentiell gewichtet (neuere Spiele zählen mehr), plus Heimvorteil der Liga.
  Ergibt Wahrscheinlichkeiten für Sieg/Unentschieden/Niederlage, erwartete Tore und die
  Über-2,5-Tore-Quote. „Value“ wird markiert, wenn das Modell ≥ 5 Prozentpunkte über der
  impliziten Buchmacher-Wahrscheinlichkeit liegt.
- **Tennis:** Ranglisten-basiert: P(Sieg Spieler 1) = R2^0,85 / (R1^0,85 + R2^0,85).
  Ohne bekanntes Ranking wird konservativ Rang 250 angenommen.

## Lokal testen

```bash
python scripts/fetch_data.py     # braucht Internetzugang
python scripts/build_site.py
open docs/index.html
```

`scripts/make_demo.py` erzeugt zusätzlich Beispieldaten (`docs/demo.html`), um das Layout
ohne Live-Daten zu prüfen.

---

*Privates Statistik-Projekt, keine Wettempfehlung. Glücksspiel kann süchtig machen (18+).*
