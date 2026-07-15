#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rendert data/data.json -> docs/index.html (komplett eigenstaendige Seite)."""

import html
import json
import os
from datetime import datetime, date

BASE = os.path.join(os.path.dirname(__file__), "..")
WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
          "August", "September", "Oktober", "November", "Dezember"]


def esc(s):
    return html.escape(str(s)) if s is not None else ""


def fmt_day_label(iso, idx):
    d = date.fromisoformat(iso)
    wd = WEEKDAYS[d.weekday()][:2]
    if idx == 0:
        return "Heute", f"{wd} {d.day:02d}.{d.month:02d}."
    if idx == 1:
        return "Morgen", f"{wd} {d.day:02d}.{d.month:02d}."
    return WEEKDAYS[d.weekday()], f"{d.day:02d}.{d.month:02d}."


def fmt_dt_long(iso):
    dt = datetime.fromisoformat(iso)
    return f"{WEEKDAYS[dt.weekday()]}, {dt.day}. {MONTHS[dt.month-1]} {dt.year}, {dt:%H:%M} Uhr"


def fmt_time(iso):
    return datetime.fromisoformat(iso).strftime("%H:%M")


def form_badges(form):
    if not form:
        return '<span class="muted small">–</span>'
    out = []
    for f in form:
        cls = {"S": "w", "U": "d", "N": "l"}.get(f, "d")
        out.append(f'<span class="fb {cls}">{f}</span>')
    return "".join(out)


def prob_bar(p_home, p_draw, p_away):
    ph, pd, pa = round(p_home * 100), round(p_draw * 100), round(p_away * 100)
    # Rundungsdifferenz auf groessten Wert schlagen
    diff = 100 - (ph + pd + pa)
    m = max((ph, "h"), (pd, "d"), (pa, "a"))
    if m[1] == "h": ph += diff
    elif m[1] == "d": pd += diff
    else: pa += diff
    seg = lambda cls, v, label: (
        f'<div class="seg {cls}" style="width:{v}%">'
        f'{f"<span>{label}&thinsp;{v}%</span>" if v >= 14 else ""}</div>')
    return (f'<div class="pbar" role="img" aria-label="Heimsieg {ph}%, Unentschieden {pd}%, Auswärtssieg {pa}%">'
            f'{seg("ph", ph, "1")}{seg("pd", pd, "X")}{seg("pa", pa, "2")}</div>')


def tennis_bar(p1, name1, name2):
    v1 = round(p1 * 100)
    v2 = 100 - v1
    return (f'<div class="pbar" role="img" aria-label="{esc(name1)} {v1}%, {esc(name2)} {v2}%">'
            f'<div class="seg ph" style="width:{v1}%">{f"<span>{v1}%</span>" if v1 >= 12 else ""}</div>'
            f'<div class="seg pa" style="width:{v2}%">{f"<span>{v2}%</span>" if v2 >= 12 else ""}</div></div>')


def odds_chips(odds, value):
    if not odds:
        return '<span class="muted small">Quoten liegen noch nicht vor</span>'
    chips = []
    for key, label in (("h", "1"), ("d", "X"), ("a", "2")):
        v = odds.get(key)
        if v is None:
            continue
        hot = ' hot' if value and value.get("outcome") == label else ''
        chips.append(f'<span class="chip{hot}"><b>{label}</b> {v:.2f}</span>')
    src = esc(odds.get("src", ""))
    return "".join(chips) + (f'<span class="muted tiny">({src})</span>' if src else "")


def value_badge(value):
    if not value:
        return ""
    edge = round(value["edge"] * 100)
    return (f'<div class="value-note">💡 Modell sieht <b>Tipp {esc(value["outcome"])}</b> bei Quote '
            f'{value["odds"]:.2f} um <b>+{edge} Prozentpunkte</b> wahrscheinlicher als der Markt.</div>')


def pos_str(pos, n):
    if not pos:
        return ""
    return f'<span class="pos">{pos}.</span>'


def match_card(m, league):
    pred = m.get("prediction")
    h2h_html = ""
    if m.get("h2h"):
        rows = "".join(
            f'<tr><td>{esc(x["date"])}</td><td>{esc(x["home"])} – {esc(x["away"])}</td>'
            f'<td class="num">{esc(x["score"])}</td></tr>' for x in m["h2h"])
        h2h_html = (f'<details class="h2h"><summary>Direkter Vergleich ({len(m["h2h"])})</summary>'
                    f'<table>{rows}</table></details>')
    pred_html = '<div class="muted small">Zu wenig Daten für eine Vorhersage</div>'
    if pred:
        pred_html = (
            prob_bar(pred["pHome"], pred["pDraw"], pred["pAway"]) +
            f'<div class="predmeta"><span>Tipp <b>{esc(pred["tipScore"])}</b></span>'
            f'<span>xG {pred["xgHome"]:.1f} : {pred["xgAway"]:.1f}</span>'
            f'<span>Über 2,5 Tore: {round(pred["pOver25"]*100)}%</span>'
            f'<span class="muted">Datenlage: {esc(pred["confidence"])}</span></div>')
    md = f'<span class="muted tiny">{m["matchday"]}. Spieltag</span>' if m.get("matchday") else ""
    return f"""
  <article class="card">
    <div class="cardtop"><span class="ko">{fmt_time(m["kickoff"])} Uhr</span>{md}</div>
    <div class="teams">
      <div class="team">
        <span class="tname">{esc(m["home"])}</span>
        <span class="tmeta">{pos_str(m.get("posHome"), m.get("nTeams"))} {form_badges(m.get("formHome"))}</span>
      </div>
      <span class="vs">:</span>
      <div class="team right">
        <span class="tname">{esc(m["away"])}</span>
        <span class="tmeta">{form_badges(m.get("formAway"))} {pos_str(m.get("posAway"), m.get("nTeams"))}</span>
      </div>
    </div>
    {pred_html}
    <div class="oddsrow">{odds_chips(m.get("odds"), m.get("value"))}</div>
    {value_badge(m.get("value"))}
    {h2h_html}
  </article>"""


def tennis_card(m):
    r1 = f'<span class="rank">#{m["p1"]["rank"]}</span>' if m["p1"].get("rank") else '<span class="rank unk">o. R.</span>'
    r2 = f'<span class="rank">#{m["p2"]["rank"]}</span>' if m["p2"].get("rank") else '<span class="rank unk">o. R.</span>'
    bar = ""
    if m.get("pP1") is not None:
        bar = tennis_bar(m["pP1"], m["p1"]["name"], m["p2"]["name"])
        fav = m["p1"]["name"] if m["pP1"] >= 0.5 else m["p2"]["name"]
        pct = round(max(m["pP1"], 1 - m["pP1"]) * 100)
        bar += f'<div class="predmeta"><span>Favorit laut Ranking: <b>{esc(fav)}</b> ({pct}%)</span></div>'
    rnd = f' · {esc(m["round"])}' if m.get("round") else ""
    unc = ('<div class="unc">⚠️ Ansetzung unbestätigt – Quelle: Community-Daten, '
           'finaler Spielplan erscheint meist erst am Vorabend</div>') if m.get("unconfirmed") else ""
    return f"""
  <article class="card">
    <div class="cardtop"><span class="ko">{fmt_time(m["start"])} Uhr</span>
      <span class="muted tiny">{esc(m["tournament"])}{rnd}</span></div>
    {unc}
    <div class="teams">
      <div class="team"><span class="tname">{esc(m["p1"]["name"])}</span><span class="tmeta">{r1}</span></div>
      <span class="vs">–</span>
      <div class="team right"><span class="tname">{esc(m["p2"]["name"])}</span><span class="tmeta">{r2}</span></div>
    </div>
    {bar}
  </article>"""


def build(data_path=None, out_path=None):
    data_path = data_path or os.path.join(BASE, "data", "data.json")
    out_path = out_path or os.path.join(BASE, "docs", "index.html")
    with open(data_path, encoding="utf-8") as f:
        data = json.load(f)

    gen = datetime.fromisoformat(data["generatedAt"])
    stand = f"{gen.day:02d}.{gen.month:02d}.{gen.year}, {gen:%H:%M} Uhr"
    season = data.get("meta", {}).get("season", "")

    # --- Tages-Tabs ---
    tabs, panels = [], []
    for i, day_iso in enumerate(data["days"]):
        label, sub = fmt_day_label(day_iso, i)
        tabs.append(f'<button class="tab{" active" if i == 0 else ""}" data-day="{i}">'
                    f'{label}<span class="tabsub">{sub}</span></button>')

        # Fussball des Tages
        fb_sections = []
        for lg in data["football"]:
            day_matches = [m for m in lg["matches"]
                           if datetime.fromisoformat(m["kickoff"]).date().isoformat() == day_iso]
            if not day_matches:
                continue
            cards = "".join(match_card(m, lg) for m in day_matches)
            fb_sections.append(
                f'<section class="league" data-cat="fussball" data-lg="{lg["id"]}">'
                f'<h2>{lg["flag"]} {esc(lg["name"])}</h2><div class="grid">{cards}</div></section>')

        # Tennis des Tages, nach Turnier gruppiert
        tn_by_tour = {}
        for m in data["tennis"]:
            if datetime.fromisoformat(m["start"]).date().isoformat() != day_iso:
                continue
            tn_by_tour.setdefault((m["tour"], m["tournament"]), []).append(m)
        tn_sections = []
        for (tour, tournament), ms in sorted(tn_by_tour.items()):
            cards = "".join(tennis_card(m) for m in sorted(ms, key=lambda x: x["start"]))
            icon = "🎾"
            tn_sections.append(
                f'<section class="league" data-cat="tennis" data-lg="{tour.lower()}">'
                f'<h2>{icon} {esc(tour)} · {esc(tournament)}</h2><div class="grid">{cards}</div></section>')

        body = "".join(fb_sections) + "".join(tn_sections)
        if not body:
            body = '<div class="empty">Für diesen Tag sind (noch) keine Partien angesetzt.</div>'
        panels.append(f'<div class="daypanel{" active" if i == 0 else ""}" data-day="{i}">{body}</div>')

    # --- Saisonpause / naechste Spiele ---
    pause_rows = []
    for lg in data["football"]:
        if lg["matches"]:
            continue
        nm = lg.get("nextMatch")
        if nm:
            md = f' ({nm["matchday"]}. Spieltag)' if nm.get("matchday") else ""
            pause_rows.append(
                f'<tr><td>{lg["flag"]} {esc(lg["name"])}</td>'
                f'<td>{fmt_dt_long(nm["kickoff"])}{md}</td>'
                f'<td>{esc(nm["home"])} – {esc(nm["away"])}</td></tr>')
        else:
            pause_rows.append(
                f'<tr><td>{lg["flag"]} {esc(lg["name"])}</td>'
                f'<td colspan="2" class="muted">Kein Termin gefunden – vermutlich Saisonpause</td></tr>')
    pause_html = ""
    if pause_rows:
        pause_html = (
            '<section class="pause"><h2>⏸️ Ligen ohne Spiele in den nächsten 3 Tagen</h2>'
            '<table class="pausetable"><thead><tr><th>Liga</th><th>Nächstes Spiel</th><th>Partie</th></tr></thead>'
            f'<tbody>{"".join(pause_rows)}</tbody></table></section>')

    n_fb = sum(len(l["matches"]) for l in data["football"])
    n_tn = len(data["tennis"])

    banner = ""
    if data.get("meta", {}).get("demo"):
        banner = ('<div class="banner">🧪 <b>Demo-Ansicht mit Beispieldaten:</b> So sieht das '
                  'Dashboard an einem Spieltag aus. Formkurven, Wahrscheinlichkeiten und Quoten '
                  'sind hier nur illustrative Beispiele.</div>')
    elif data.get("meta", {}).get("preview"):
        banner = ('<div class="banner">👋 <b>Vorschau:</b> Diese Seite zeigt den aktuellen Stand. '
                  'Tennis-Rankings, exakte Anstoßzeiten und Quoten werden ab dem ersten '
                  'automatischen Update vollständig befüllt.</div>')

    html_doc = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sport-Radar · Spiele &amp; Analysen der nächsten 3 Tage</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>⚽</text></svg>">
<style>
:root {{
  color-scheme: light;
  --page: #f9f9f7; --surface: #fcfcfb; --ink: #0b0b0b; --ink2: #52514e;
  --muted: #898781; --grid: #e1e0d9; --border: rgba(11,11,11,.10);
  --home: #2a78d6; --away: #eb6834; --draw: #f0efec; --draw-ink: #52514e;
  --good: #0ca30c; --bad: #d03b3b; --accent: #2a78d6;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    color-scheme: dark;
    --page: #0d0d0d; --surface: #1a1a19; --ink: #fff; --ink2: #c3c2b7;
    --muted: #898781; --grid: #2c2c2a; --border: rgba(255,255,255,.10);
    --home: #3987e5; --away: #d95926; --draw: #383835; --draw-ink: #c3c2b7;
    --good: #0ca30c; --bad: #e66767; --accent: #3987e5;
  }}
}}
* {{ box-sizing: border-box; }}
body {{ margin:0; background:var(--page); color:var(--ink);
  font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif; }}
header {{ padding:22px 18px 10px; max-width:1100px; margin:0 auto; }}
h1 {{ font-size:24px; margin:0 0 2px; }}
.sub {{ color:var(--ink2); font-size:13px; }}
main {{ max-width:1100px; margin:0 auto; padding:0 18px 40px; }}
.tabs {{ display:flex; gap:8px; margin:16px 0 6px; flex-wrap:wrap; }}
.tab {{ background:var(--surface); border:1px solid var(--border); border-radius:10px;
  padding:8px 16px; font:inherit; font-weight:600; color:var(--ink2); cursor:pointer;
  display:flex; flex-direction:column; align-items:center; min-width:96px; }}
.tab .tabsub {{ font-weight:400; font-size:11px; color:var(--muted); }}
.tab.active {{ color:var(--ink); border-color:var(--accent); box-shadow:inset 0 -2px 0 var(--accent); }}
.filters {{ display:flex; gap:6px; margin:10px 0 4px; flex-wrap:wrap; }}
.flt {{ background:none; border:1px solid var(--border); border-radius:999px; padding:4px 12px;
  font:inherit; font-size:13px; color:var(--ink2); cursor:pointer; }}
.flt.active {{ background:var(--surface); color:var(--ink); border-color:var(--accent); font-weight:600; }}
.daypanel {{ display:none; }} .daypanel.active {{ display:block; }}
.league {{ margin-top:22px; }}
.league h2 {{ font-size:16px; margin:0 0 10px; border-bottom:1px solid var(--grid); padding-bottom:6px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(330px,1fr)); gap:12px; }}
.card {{ background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:12px 14px; }}
.cardtop {{ display:flex; justify-content:space-between; align-items:baseline; gap:8px; margin-bottom:8px; }}
.ko {{ font-weight:700; font-size:13px; }}
.teams {{ display:flex; align-items:flex-start; gap:8px; margin-bottom:10px; }}
.team {{ flex:1; min-width:0; display:flex; flex-direction:column; gap:3px; }}
.team.right {{ text-align:right; align-items:flex-end; }}
.tname {{ font-weight:650; font-size:14.5px; }}
.tmeta {{ display:flex; gap:4px; align-items:center; }}
.vs {{ color:var(--muted); font-weight:600; padding-top:1px; }}
.pos {{ font-size:11px; color:var(--ink2); border:1px solid var(--grid); border-radius:5px;
  padding:0 4px; }}
.fb {{ display:inline-block; width:17px; height:17px; border-radius:5px; font-size:10.5px;
  font-weight:700; text-align:center; line-height:17px; color:#fff; }}
.fb.w {{ background:var(--good); }} .fb.l {{ background:var(--bad); }}
.fb.d {{ background:var(--draw); color:var(--draw-ink); border:1px solid var(--grid); line-height:15px; }}
.pbar {{ display:flex; height:22px; border-radius:6px; overflow:hidden; gap:2px; background:var(--page); }}
.seg {{ display:flex; align-items:center; justify-content:center; font-size:11px; font-weight:700;
  color:#fff; min-width:0; white-space:nowrap; overflow:hidden; }}
.seg.ph {{ background:var(--home); border-radius:6px 0 0 6px; }}
.seg.pd {{ background:var(--draw); color:var(--draw-ink); }}
.seg.pa {{ background:var(--away); border-radius:0 6px 6px 0; }}
.predmeta {{ display:flex; gap:12px; flex-wrap:wrap; font-size:12px; color:var(--ink2); margin-top:6px; }}
.oddsrow {{ display:flex; gap:6px; align-items:center; margin-top:9px; flex-wrap:wrap; }}
.chip {{ border:1px solid var(--grid); border-radius:7px; padding:2px 9px; font-size:12.5px; }}
.chip b {{ color:var(--ink2); margin-right:3px; font-weight:600; }}
.chip.hot {{ border-color:var(--accent); box-shadow:inset 0 0 0 1px var(--accent); }}
.value-note {{ margin-top:8px; font-size:12.5px; background:var(--page); border:1px dashed var(--border);
  border-radius:8px; padding:6px 9px; color:var(--ink2); }}
.h2h {{ margin-top:8px; font-size:12.5px; }}
.h2h summary {{ cursor:pointer; color:var(--ink2); }}
.h2h table {{ width:100%; border-collapse:collapse; margin-top:6px; }}
.h2h td {{ padding:3px 4px; border-top:1px solid var(--grid); color:var(--ink2); }}
.h2h td.num {{ text-align:right; font-variant-numeric:tabular-nums; color:var(--ink); }}
.rank {{ font-size:11.5px; color:var(--ink2); border:1px solid var(--grid); border-radius:5px; padding:0 5px; }}
.rank.unk {{ color:var(--muted); border-style:dashed; }}
.empty {{ margin:26px 0; color:var(--muted); text-align:center; padding:30px;
  border:1px dashed var(--border); border-radius:12px; }}
.pause {{ margin-top:30px; }}
.pause h2 {{ font-size:15px; }}
.pausetable {{ width:100%; border-collapse:collapse; background:var(--surface);
  border:1px solid var(--border); border-radius:10px; overflow:hidden; font-size:13px; }}
.pausetable th {{ text-align:left; padding:8px 10px; color:var(--muted); font-weight:600;
  border-bottom:1px solid var(--grid); font-size:12px; }}
.pausetable td {{ padding:8px 10px; border-bottom:1px solid var(--grid); }}
.pausetable tr:last-child td {{ border-bottom:none; }}
footer {{ max-width:1100px; margin:0 auto; padding:18px; color:var(--muted); font-size:12px; }}
footer details {{ margin-bottom:10px; color:var(--ink2); }}
footer summary {{ cursor:pointer; }}
.muted {{ color:var(--muted); }} .small {{ font-size:12.5px; }} .tiny {{ font-size:11.5px; }}
.disclaimer {{ border-top:1px solid var(--grid); padding-top:10px; margin-top:10px; }}
.banner {{ background:var(--surface); border:1px solid var(--accent); border-radius:10px;
  padding:9px 13px; font-size:13px; color:var(--ink2); margin:12px 0 0; }}
.unc {{ font-size:11.5px; color:var(--ink2); border:1px dashed var(--border); border-radius:7px;
  padding:4px 8px; margin-bottom:8px; }}
</style>
</head>
<body>
<header>
  <h1>⚽ Sport-Radar 🎾</h1>
  <div class="sub">Spiele &amp; Analysen der nächsten 3 Tage · Saison {esc(season)} ·
    Stand: <b>{stand}</b> · {n_fb} Fußballspiele · {n_tn} Tennis-Matches</div>
  {banner}
  <div class="tabs">{"".join(tabs)}</div>
  <div class="filters">
    <button class="flt active" data-f="alle">Alle</button>
    <button class="flt" data-f="fussball">⚽ Fußball</button>
    <button class="flt" data-f="tennis">🎾 Tennis</button>
  </div>
</header>
<main>
{"".join(panels)}
{pause_html}
</main>
<footer>
  <details>
    <summary>Wie funktionieren die Vorhersagen?</summary>
    <p>Fußball: Poisson-Modell auf Basis der Ergebnisse der letzten zwei Saisons (neuere Spiele
    zählen stärker), inkl. Heimvorteil. Daraus ergeben sich Wahrscheinlichkeiten für 1/X/2,
    erwartete Tore (xG) und ein wahrscheinlichstes Ergebnis. „Value“ markiert Fälle, in denen das
    Modell ein Ergebnis deutlich wahrscheinlicher einschätzt als die Buchmacher-Quote. Tennis:
    Einschätzung anhand der aktuellen Weltranglisten-Position beider Spieler:innen („o. R.“ = ohne
    Ranking in den Top-Platzierungen). Alle Angaben sind statistische Schätzungen ohne Gewähr.</p>
  </details>
  <div>Datenquellen: OpenLigaDB (1.–3. Bundesliga), ESPN (internationale Ligen, Tennis, Rankings),
  football-data.co.uk (Quoten &amp; Historie), TheSportsDB (Tennis-Ergänzung).
  Automatisches Update: täglich.</div>
  <div class="disclaimer">Dieses Dashboard ist ein privates Statistik-Projekt und keine
  Wettempfehlung. Quoten dienen nur dem Vergleich mit dem Modell. Glücksspiel kann süchtig
  machen (18+) – Hilfe: <a href="https://www.bundesweit-gegen-gluecksspielsucht.de">bundesweit-gegen-gluecksspielsucht.de</a>.</div>
</footer>
<script>
document.querySelectorAll('.tab').forEach(t => t.addEventListener('click', () => {{
  document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
  document.querySelectorAll('.daypanel').forEach(x => x.classList.remove('active'));
  t.classList.add('active');
  document.querySelector('.daypanel[data-day="' + t.dataset.day + '"]').classList.add('active');
}}));
document.querySelectorAll('.flt').forEach(b => b.addEventListener('click', () => {{
  document.querySelectorAll('.flt').forEach(x => x.classList.remove('active'));
  b.classList.add('active');
  const f = b.dataset.f;
  document.querySelectorAll('.league').forEach(sec => {{
    sec.style.display = (f === 'alle' || sec.dataset.cat === f) ? '' : 'none';
  }});
}}));
</script>
</body>
</html>"""

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_doc)
    print(f"OK -> {out_path}  ({len(html_doc)//1024} kB)")


if __name__ == "__main__":
    import sys
    build(sys.argv[1] if len(sys.argv) > 1 else None,
          sys.argv[2] if len(sys.argv) > 2 else None)
