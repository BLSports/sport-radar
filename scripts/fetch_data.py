#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sport-Analyse-Dashboard: Daten-Pipeline
Holt Spiele der naechsten 3 Tage + Statistiken + Quoten und berechnet Vorhersagen.

Quellen (alle kostenlos):
  - OpenLigaDB          -> 1./2./3. Bundesliga (Spielplaene + Ergebnisse)
  - ESPN (inoffiziell)  -> Premier League, Serie A, La Liga 1+2 (Spielplaene), ATP/WTA (Matches, Rankings)
  - football-data.co.uk -> historische Ergebnisse + Quoten (grosse Ligen)
  - TheSportsDB         -> Tennis-Fallback
  - The Odds API        -> optional, nur wenn ODDS_API_KEY gesetzt (3. Liga + Tennis-Quoten)

Ausgabe: data/data.json
"""

import csv
import io
import json
import math
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

BERLIN_UTC_OFFSET = None  # wird via zoneinfo bestimmt
try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Europe/Berlin")
except Exception:
    TZ = timezone(timedelta(hours=2))

UA = {"User-Agent": "Mozilla/5.0 (SportDashboard/1.0; private hobby project)"}
DAYS_AHEAD = 3
ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "").strip()

NOW = datetime.now(TZ)
TODAY = NOW.date()


# ----------------------------------------------------------------------------
# HTTP-Helfer
# ----------------------------------------------------------------------------

def http_get(url, retries=3, timeout=25, as_json=True):
    last_err = None
    for attempt in range(retries):
        try:
            req = Request(url, headers=UA)
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            if as_json:
                return json.loads(raw.decode("utf-8", errors="replace"))
            return raw.decode("utf-8", errors="replace")
        except (URLError, HTTPError, json.JSONDecodeError, TimeoutError) as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    print(f"  WARN: {url} nicht erreichbar ({last_err})", file=sys.stderr)
    return None


# ----------------------------------------------------------------------------
# Team-Namen-Normalisierung (ESPN vs. football-data.co.uk vs. OpenLigaDB)
# ----------------------------------------------------------------------------

ALIASES = {
    # Premier League
    "manchester united": "man united", "manchester utd": "man united",
    "manchester city": "man city",
    "newcastle united": "newcastle", "newcastle utd": "newcastle",
    "tottenham hotspur": "tottenham", "spurs": "tottenham",
    "wolverhampton wanderers": "wolves", "wolverhampton": "wolves",
    "nottingham forest": "nott'm forest", "nottm forest": "nott'm forest",
    "west ham united": "west ham",
    "brighton & hove albion": "brighton", "brighton and hove albion": "brighton",
    "afc bournemouth": "bournemouth",
    "leeds united": "leeds",
    "leicester city": "leicester",
    "sheffield united": "sheffield utd",
    "afc sunderland": "sunderland",
    # Serie A
    "internazionale": "inter", "inter milan": "inter", "inter mailand": "inter",
    "ac milan": "milan", "ac mailand": "milan",
    "as roma": "roma",
    "ss lazio": "lazio",
    "ssc napoli": "napoli",
    "juventus turin": "juventus",
    "acf fiorentina": "fiorentina", "ac fiorentina": "fiorentina",
    "hellas verona": "verona",
    "us sassuolo": "sassuolo",
    "udinese calcio": "udinese",
    "atalanta bc": "atalanta", "atalanta bergamo": "atalanta",
    "bologna fc": "bologna",
    "torino fc": "torino",
    "genoa cfc": "genoa",
    "cagliari calcio": "cagliari",
    "us lecce": "lecce",
    "parma calcio": "parma",
    "como 1907": "como",
    "us cremonese": "cremonese",
    "delfino pescara": "pescara",
    # La Liga
    "atletico madrid": "ath madrid", "atlético madrid": "ath madrid", "atletico de madrid": "ath madrid",
    "athletic club": "ath bilbao", "athletic bilbao": "ath bilbao",
    "real sociedad": "sociedad",
    "real betis": "betis",
    "celta vigo": "celta", "rc celta": "celta", "celta de vigo": "celta",
    "rayo vallecano": "vallecano",
    "deportivo alaves": "alaves", "deportivo alavés": "alaves",
    "real valladolid": "valladolid",
    "rcd espanyol": "espanol", "espanyol": "espanol", "espanyol barcelona": "espanol",
    "rcd mallorca": "mallorca",
    "real oviedo": "oviedo",
    "ud las palmas": "las palmas",
    "cadiz cf": "cadiz",
    "getafe cf": "getafe",
    "girona fc": "girona",
    "sevilla fc": "sevilla",
    "valencia cf": "valencia",
    "villarreal cf": "villarreal",
    "elche cf": "elche",
    "levante ud": "levante",
    "ca osasuna": "osasuna",
    # La Liga 2 (häufige)
    "sporting gijon": "sp gijon", "sporting de gijon": "sp gijon",
    "deportivo la coruna": "la coruna", "deportivo de la coruna": "la coruna", "rc deportivo": "la coruna",
    "real zaragoza": "zaragoza",
    "cd tenerife": "tenerife",
    "ud almeria": "almeria",
    "racing santander": "santander", "real racing club": "santander",
    "cd leganes": "leganes",
    "granada cf": "granada",
    "cd castellon": "castellon",
    "burgos cf": "burgos",
    "cd mirandes": "mirandes",
    "sd eibar": "eibar",
    "sd huesca": "huesca",
    "cordoba cf": "cordoba",
    "malaga cf": "malaga",
    "albacete balompie": "albacete",
    "cadiz": "cadiz",
    "fc andorra": "andorra",
    "ceuta": "ceuta", "ad ceuta": "ceuta",
    "real sociedad b": "sociedad b",
    "cultural leonesa": "cul leonesa", "cultural y deportiva leonesa": "cul leonesa",
}


def norm_team(name):
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = ALIASES.get(s, s)
    return s


def team_match(a, b):
    """Fuzzy-Vergleich zweier (bereits normalisierter) Teamnamen."""
    if a == b:
        return True
    if a and b and (a in b or b in a) and min(len(a), len(b)) >= 4:
        return True
    return SequenceMatcher(None, a, b).ratio() >= 0.82


# ----------------------------------------------------------------------------
# Fussball: Ligen-Konfiguration
# ----------------------------------------------------------------------------

LEAGUES = [
    {"id": "bl1", "name": "1. Bundesliga", "country": "DE", "flag": "\U0001F1E9\U0001F1EA",
     "source": "openligadb", "oldb": "bl1", "fdcuk": "D1"},
    {"id": "bl2", "name": "2. Bundesliga", "country": "DE", "flag": "\U0001F1E9\U0001F1EA",
     "source": "openligadb", "oldb": "bl2", "fdcuk": "D2"},
    {"id": "bl3", "name": "3. Liga", "country": "DE", "flag": "\U0001F1E9\U0001F1EA",
     "source": "openligadb", "oldb": "bl3", "fdcuk": None},
    {"id": "pl", "name": "Premier League", "country": "EN", "flag": "\U0001F3F4\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F",
     "source": "espn", "espn": "eng.1", "fdcuk": "E0"},
    {"id": "sa", "name": "Serie A", "country": "IT", "flag": "\U0001F1EE\U0001F1F9",
     "source": "espn", "espn": "ita.1", "fdcuk": "I1"},
    {"id": "ll1", "name": "La Liga", "country": "ES", "flag": "\U0001F1EA\U0001F1F8",
     "source": "espn", "espn": "esp.1", "fdcuk": "SP1"},
    {"id": "ll2", "name": "La Liga 2", "country": "ES", "flag": "\U0001F1EA\U0001F1F8",
     "source": "espn", "espn": "esp.2", "fdcuk": "SP2"},
]


def current_season_year():
    """Fussball-Saisonjahr: ab Juli -> aktuelles Jahr (Saison 2026/27 == 2026)."""
    return NOW.year if NOW.month >= 7 else NOW.year - 1


def fdcuk_season_code(year):
    """2026 -> '2627'"""
    return f"{str(year)[2:]}{str(year + 1)[2:]}"


# ----------------------------------------------------------------------------
# Fussball: Ergebnisse laden (fuer Form + Modell)
# ----------------------------------------------------------------------------

def load_results_openligadb(shortcut, years):
    """Alle beendeten Spiele der angegebenen Saisons."""
    results = []
    for y in years:
        data = http_get(f"https://api.openligadb.de/getmatchdata/{shortcut}/{y}")
        if not data:
            continue
        for m in data:
            if not m.get("matchIsFinished"):
                continue
            res = next((r for r in m.get("matchResults", [])
                        if r.get("resultTypeID") == 2), None)
            if res is None and m.get("matchResults"):
                res = m["matchResults"][-1]
            if res is None:
                continue
            try:
                dt = datetime.fromisoformat(m["matchDateTimeUTC"].replace("Z", "+00:00"))
            except Exception:
                continue
            results.append({
                "date": dt,
                "home": m["team1"]["teamName"], "away": m["team2"]["teamName"],
                "hg": res.get("pointsTeam1", 0), "ag": res.get("pointsTeam2", 0),
            })
    return results


def load_results_fdcuk(code, years):
    """Ergebnisse von football-data.co.uk CSVs."""
    results = []
    for y in years:
        url = f"https://www.football-data.co.uk/mmz4281/{fdcuk_season_code(y)}/{code}.csv"
        raw = http_get(url, as_json=False)
        if not raw:
            continue
        try:
            reader = csv.DictReader(io.StringIO(raw))
            for row in reader:
                d, hg, ag = row.get("Date"), row.get("FTHG"), row.get("FTAG")
                if not d or hg in (None, "") or ag in (None, ""):
                    continue
                try:
                    if len(d.split("/")[-1]) == 4:
                        dt = datetime.strptime(d, "%d/%m/%Y")
                    else:
                        dt = datetime.strptime(d, "%d/%m/%y")
                    dt = dt.replace(tzinfo=TZ)
                except Exception:
                    continue
                results.append({
                    "date": dt,
                    "home": row.get("HomeTeam", ""), "away": row.get("AwayTeam", ""),
                    "hg": int(float(hg)), "ag": int(float(ag)),
                    "odds": _extract_odds_row(row),
                })
        except Exception as e:
            print(f"  WARN: CSV {url}: {e}", file=sys.stderr)
    return results


def _extract_odds_row(row):
    for pre in ("Avg", "B365", "PS", "Max"):
        h, d, a = row.get(f"{pre}H"), row.get(f"{pre}D"), row.get(f"{pre}A")
        if h and d and a:
            try:
                return {"h": float(h), "d": float(d), "a": float(a), "src": pre}
            except ValueError:
                pass
    return None


def load_results_espn(slug, years):
    """Fallback: ESPN-Scoreboard je Saison abgrasen ist teuer; wir nutzen ESPN nur,
    wenn football-data.co.uk nichts liefert (z.B. Saisonbeginn)."""
    results = []
    start = datetime(years[0], 7, 1)
    end = min(NOW.replace(tzinfo=None), datetime(years[-1] + 1, 6, 30))
    url = (f"https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard"
           f"?dates={start:%Y%m%d}-{end:%Y%m%d}&limit=1000")
    data = http_get(url)
    if not data:
        return results
    for ev in data.get("events", []):
        try:
            comp = ev["competitions"][0]
            if comp.get("status", {}).get("type", {}).get("completed") is not True:
                continue
            dt = datetime.fromisoformat(ev["date"].replace("Z", "+00:00"))
            home = next(c for c in comp["competitors"] if c["homeAway"] == "home")
            away = next(c for c in comp["competitors"] if c["homeAway"] == "away")
            results.append({
                "date": dt,
                "home": home["team"]["displayName"], "away": away["team"]["displayName"],
                "hg": int(home.get("score", 0)), "ag": int(away.get("score", 0)),
            })
        except Exception:
            continue
    return results


# ----------------------------------------------------------------------------
# Fussball: kommende Spiele (naechste 3 Tage) + naechster Spieltag
# ----------------------------------------------------------------------------

def upcoming_openligadb(shortcut, year):
    data = http_get(f"https://api.openligadb.de/getmatchdata/{shortcut}/{year}")
    if not data:
        return [], None
    upcoming, first_future = [], None
    for m in data:
        if m.get("matchIsFinished"):
            continue
        try:
            dt = datetime.fromisoformat(m["matchDateTimeUTC"].replace("Z", "+00:00")).astimezone(TZ)
        except Exception:
            continue
        if dt < NOW - timedelta(hours=3):
            continue
        entry = {"dt": dt, "home": m["team1"]["teamName"], "away": m["team2"]["teamName"],
                 "homeIcon": m["team1"].get("teamIconUrl"), "awayIcon": m["team2"].get("teamIconUrl"),
                 "matchday": (m.get("group") or {}).get("groupOrderID")}
        if first_future is None or dt < first_future["dt"]:
            first_future = entry
        if TODAY <= dt.date() <= TODAY + timedelta(days=DAYS_AHEAD - 1):
            upcoming.append(entry)
    return upcoming, first_future


def upcoming_espn(slug):
    upcoming = []
    for i in range(DAYS_AHEAD):
        d = TODAY + timedelta(days=i)
        data = http_get(f"https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard?dates={d:%Y%m%d}")
        if not data:
            continue
        for ev in data.get("events", []):
            try:
                comp = ev["competitions"][0]
                state = comp.get("status", {}).get("type", {}).get("state")
                if state not in ("pre",):
                    continue
                dt = datetime.fromisoformat(ev["date"].replace("Z", "+00:00")).astimezone(TZ)
                home = next(c for c in comp["competitors"] if c["homeAway"] == "home")
                away = next(c for c in comp["competitors"] if c["homeAway"] == "away")
                upcoming.append({
                    "dt": dt,
                    "home": home["team"]["displayName"], "away": away["team"]["displayName"],
                    "homeIcon": (home["team"].get("logos") or [{}])[0].get("href") if home["team"].get("logos") else home["team"].get("logo"),
                    "awayIcon": (away["team"].get("logos") or [{}])[0].get("href") if away["team"].get("logos") else away["team"].get("logo"),
                    "matchday": None,
                })
            except Exception:
                continue
    # naechstes Spiel ausserhalb des Fensters suchen (fuer "Saisonpause"-Anzeige)
    first_future = None
    if not upcoming:
        end = TODAY + timedelta(days=120)
        data = http_get(f"https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard"
                        f"?dates={TODAY:%Y%m%d}-{end:%Y%m%d}&limit=50")
        if data:
            for ev in data.get("events", []):
                try:
                    comp = ev["competitions"][0]
                    if comp.get("status", {}).get("type", {}).get("state") != "pre":
                        continue
                    dt = datetime.fromisoformat(ev["date"].replace("Z", "+00:00")).astimezone(TZ)
                    home = next(c for c in comp["competitors"] if c["homeAway"] == "home")
                    away = next(c for c in comp["competitors"] if c["homeAway"] == "away")
                    e = {"dt": dt, "home": home["team"]["displayName"],
                         "away": away["team"]["displayName"], "matchday": None}
                    if first_future is None or dt < first_future["dt"]:
                        first_future = e
                except Exception:
                    continue
    return upcoming, first_future


# ----------------------------------------------------------------------------
# Vorhersage-Modell (Poisson mit Zeitabklingen)
# ----------------------------------------------------------------------------

DECAY_HALF_LIFE_DAYS = 240.0


def _weight(days_ago):
    return 0.5 ** (max(days_ago, 0) / DECAY_HALF_LIFE_DAYS)


def build_strengths(results):
    """Angriffs-/Abwehrstaerken je Team (normalisiert), plus Heimvorteil."""
    if not results:
        return {}, 1.4, 1.15
    tw = {}   # team -> [w_sum, gf_w, ga_w]
    total_w = total_goals_w = 0.0
    home_goals_w = away_goals_w = 0.0
    for r in results:
        days = (NOW - (r["date"] if r["date"].tzinfo else r["date"].replace(tzinfo=TZ))).days
        w = _weight(days)
        h, a = norm_team(r["home"]), norm_team(r["away"])
        for team, gf, ga in ((h, r["hg"], r["ag"]), (a, r["ag"], r["hg"])):
            t = tw.setdefault(team, [0.0, 0.0, 0.0])
            t[0] += w
            t[1] += w * gf
            t[2] += w * ga
        total_w += w
        total_goals_w += w * (r["hg"] + r["ag"])
        home_goals_w += w * r["hg"]
        away_goals_w += w * r["ag"]
    league_avg = (total_goals_w / (2 * total_w)) if total_w else 1.4
    home_adv = (home_goals_w / away_goals_w) ** 0.5 if away_goals_w > 0 else 1.15
    strengths = {}
    for team, (w, gf, ga) in tw.items():
        if w < 2:   # zu wenig Daten
            strengths[team] = (1.0, 1.0, w)
            continue
        att = (gf / w) / league_avg
        dfn = (ga / w) / league_avg
        strengths[team] = (att, dfn, w)
    return strengths, league_avg, home_adv


def find_team(strengths, name):
    n = norm_team(name)
    if n in strengths:
        return strengths[n]
    for key, val in strengths.items():
        if team_match(n, key):
            return val
    return None


def poisson_probs(mu_h, mu_a, max_goals=9):
    ph = [math.exp(-mu_h) * mu_h ** k / math.factorial(k) for k in range(max_goals + 1)]
    pa = [math.exp(-mu_a) * mu_a ** k / math.factorial(k) for k in range(max_goals + 1)]
    p_home = p_draw = p_away = p_over25 = 0.0
    best_score, best_p = (0, 0), -1.0
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            p = ph[i] * pa[j]
            if i > j:
                p_home += p
            elif i == j:
                p_draw += p
            else:
                p_away += p
            if i + j >= 3:
                p_over25 += p
            if p > best_p:
                best_p, best_score = p, (i, j)
    return p_home, p_draw, p_away, p_over25, best_score


def predict_match(strengths, league_avg, home_adv, home, away):
    sh, sa = find_team(strengths, home), find_team(strengths, away)
    if sh is None or sa is None:
        return None
    att_h, def_h, wh = sh
    att_a, def_a, wa = sa
    mu_h = max(0.15, league_avg * att_h * def_a * home_adv)
    mu_a = max(0.1, league_avg * att_a * def_h / home_adv)
    p_h, p_d, p_a, p_o25, score = poisson_probs(mu_h, mu_a)
    conf = "hoch" if min(wh, wa) >= 8 else ("mittel" if min(wh, wa) >= 4 else "niedrig")
    return {
        "pHome": round(p_h, 4), "pDraw": round(p_d, 4), "pAway": round(p_a, 4),
        "pOver25": round(p_o25, 4),
        "xgHome": round(mu_h, 2), "xgAway": round(mu_a, 2),
        "tipScore": f"{score[0]}:{score[1]}",
        "confidence": conf,
    }


# ----------------------------------------------------------------------------
# Form, Tabelle, H2H
# ----------------------------------------------------------------------------

def team_form(results, team, n=5):
    n_t = norm_team(team)
    played = []
    for r in sorted(results, key=lambda x: x["date"]):
        h, a = norm_team(r["home"]), norm_team(r["away"])
        if team_match(n_t, h):
            played.append("S" if r["hg"] > r["ag"] else ("U" if r["hg"] == r["ag"] else "N"))
        elif team_match(n_t, a):
            played.append("S" if r["ag"] > r["hg"] else ("U" if r["hg"] == r["ag"] else "N"))
    return played[-n:]


def compute_table(results, season_start):
    table = {}
    for r in results:
        if r["date"].replace(tzinfo=r["date"].tzinfo or TZ) < season_start:
            continue
        h, a = norm_team(r["home"]), norm_team(r["away"])
        for t in (h, a):
            table.setdefault(t, {"pts": 0, "gd": 0, "gp": 0, "name": None})
        table[h]["name"] = table[h]["name"] or r["home"]
        table[a]["name"] = table[a]["name"] or r["away"]
        table[h]["gp"] += 1
        table[a]["gp"] += 1
        table[h]["gd"] += r["hg"] - r["ag"]
        table[a]["gd"] += r["ag"] - r["hg"]
        if r["hg"] > r["ag"]:
            table[h]["pts"] += 3
        elif r["hg"] < r["ag"]:
            table[a]["pts"] += 3
        else:
            table[h]["pts"] += 1
            table[a]["pts"] += 1
    ranked = sorted(table.items(), key=lambda kv: (-kv[1]["pts"], -kv[1]["gd"]))
    return {team: i + 1 for i, (team, _) in enumerate(ranked)}, len(ranked)


def table_pos(table, team):
    n = norm_team(team)
    if n in table:
        return table[n]
    for k, v in table.items():
        if team_match(n, k):
            return v
    return None


def head_to_head(results, home, away, n=5):
    nh, na = norm_team(home), norm_team(away)
    meetings = []
    for r in sorted(results, key=lambda x: x["date"], reverse=True):
        rh, ra = norm_team(r["home"]), norm_team(r["away"])
        if (team_match(nh, rh) and team_match(na, ra)) or (team_match(nh, ra) and team_match(na, rh)):
            meetings.append({
                "date": r["date"].strftime("%d.%m.%Y"),
                "home": r["home"], "away": r["away"],
                "score": f"{r['hg']}:{r['ag']}",
            })
        if len(meetings) >= n:
            break
    return meetings


# ----------------------------------------------------------------------------
# Quoten (football-data.co.uk fixtures.csv + optional The Odds API)
# ----------------------------------------------------------------------------

def load_fixture_odds_fdcuk():
    """fixtures.csv enthaelt Quoten fuer anstehende Spiele der grossen Ligen."""
    raw = http_get("https://www.football-data.co.uk/fixtures.csv", as_json=False)
    odds = {}
    if not raw:
        return odds
    try:
        reader = csv.DictReader(io.StringIO(raw))
        for row in reader:
            div = row.get("Div", "")
            o = _extract_odds_row(row)
            if not o:
                continue
            key = (div, norm_team(row.get("HomeTeam", "")), norm_team(row.get("AwayTeam", "")))
            odds[key] = o
    except Exception as e:
        print(f"  WARN fixtures.csv: {e}", file=sys.stderr)
    return odds


def find_odds(odds_map, div, home, away):
    if not div:
        return None
    nh, na = norm_team(home), norm_team(away)
    direct = odds_map.get((div, nh, na))
    if direct:
        return direct
    for (d, h, a), o in odds_map.items():
        if d == div and team_match(nh, h) and team_match(na, a):
            return o
    return None


def odds_api_get(sport_key):
    if not ODDS_API_KEY:
        return []
    url = (f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
           f"?apiKey={ODDS_API_KEY}&regions=eu&markets=h2h&oddsFormat=decimal")
    return http_get(url) or []


def odds_api_football(sport_key, home, away):
    """Sucht 1X2-Quoten fuer ein Spiel bei The Odds API (falls Key gesetzt)."""
    events = odds_api_cache.get(sport_key)
    if events is None:
        events = odds_api_get(sport_key)
        odds_api_cache[sport_key] = events
    nh, na = norm_team(home), norm_team(away)
    for ev in events:
        eh, ea = norm_team(ev.get("home_team", "")), norm_team(ev.get("away_team", ""))
        if not (team_match(nh, eh) and team_match(na, ea)):
            continue
        for bm in ev.get("bookmakers", []):
            for market in bm.get("markets", []):
                if market.get("key") != "h2h":
                    continue
                out = {o.get("name"): o.get("price") for o in market.get("outcomes", [])}
                h = out.get(ev.get("home_team"))
                a = out.get(ev.get("away_team"))
                d = out.get("Draw")
                if h and a:
                    return {"h": h, "d": d, "a": a, "src": bm.get("title", "OddsAPI")}
    return None


odds_api_cache = {}

ODDS_API_SPORT_KEYS = {
    "bl1": "soccer_germany_bundesliga",
    "bl2": "soccer_germany_bundesliga2",
    "bl3": "soccer_germany_liga3",
    "pl": "soccer_epl",
    "sa": "soccer_italy_serie_a",
    "ll1": "soccer_spain_la_liga",
    "ll2": "soccer_spain_segunda_division",
}


def implied_probs(o):
    """Normalisierte implizite Wahrscheinlichkeiten aus 1X2-Quoten."""
    try:
        inv = [1.0 / o["h"], 1.0 / o["d"], 1.0 / o["a"]]
    except (TypeError, ZeroDivisionError, KeyError):
        return None
    s = sum(inv)
    return [x / s for x in inv]


# ----------------------------------------------------------------------------
# Tennis (ESPN + TheSportsDB)
# ----------------------------------------------------------------------------

def espn_tennis_day(tour, day):
    """Angesetzte Matches eines Tages, tour in {atp, wta}."""
    data = http_get(f"https://site.api.espn.com/apis/site/v2/sports/tennis/{tour}/scoreboard?dates={day:%Y%m%d}")
    matches = []
    if not data:
        return matches
    for ev in data.get("events", []):
        tour_name = ev.get("name", "")
        loc = (ev.get("locations") or [{}])
        venue = ""
        try:
            venue = ev.get("circuit", {}).get("fullName", "") or ""
        except Exception:
            pass
        groupings = ev.get("groupings") or []
        comps = []
        for g in groupings:
            gname = (g.get("grouping") or {}).get("displayName", "")
            if "doubles" in gname.lower():
                continue
            comps.extend([(c, gname) for c in g.get("competitions", [])])
        if not groupings:
            comps = [(c, "") for c in ev.get("competitions", [])]
        for comp, gname in comps:
            try:
                st = comp.get("status", {}).get("type", {})
                if st.get("state") != "pre":
                    continue
                dt = datetime.fromisoformat(comp["date"].replace("Z", "+00:00")).astimezone(TZ)
                if dt.date() != day:
                    continue
                players = []
                for c in comp.get("competitors", []):
                    ath = c.get("athlete", {}) or {}
                    players.append({
                        "name": ath.get("displayName") or ath.get("shortName") or "?",
                        "id": str(ath.get("id", "")),
                        "seed": c.get("curatedRank", {}).get("current") if isinstance(c.get("curatedRank"), dict) else None,
                    })
                if len(players) != 2:
                    continue
                matches.append({
                    "dt": dt, "tour": tour.upper(), "tournament": tour_name,
                    "round": comp.get("round", {}).get("displayName", "") if isinstance(comp.get("round"), dict) else (comp.get("note") or gname),
                    "p1": players[0], "p2": players[1], "venue": venue,
                    "src": "espn",
                })
            except Exception:
                continue
    return matches


def tsdb_tennis_day(day):
    data = http_get(f"https://www.thesportsdb.com/api/v1/json/123/eventsday.php?d={day:%Y-%m-%d}&s=Tennis")
    matches = []
    if not data or not data.get("events"):
        return matches
    for ev in data["events"]:
        league = ev.get("strLeague", "")
        tour = "ATP" if "ATP" in league.upper() else ("WTA" if "WTA" in league.upper() else None)
        if not tour:
            continue
        name = ev.get("strEvent", "")
        m = re.search(r"(.+?)\s+(\S+(?:\s\S+)?)\s+vs\s+(.+)$", name)
        if not m:
            continue
        tournament, p1, p2 = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
        t = ev.get("strTime") or "00:00:00"
        try:
            dt = datetime.strptime(f"{ev['dateEvent']} {t}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).astimezone(TZ)
        except Exception:
            continue
        matches.append({
            "dt": dt, "tour": tour, "tournament": tournament, "round": "",
            "p1": {"name": p1, "id": "", "seed": None},
            "p2": {"name": p2, "id": "", "seed": None},
            "venue": "",
            "src": "tsdb",
        })
    return matches


def espn_rankings(tour):
    """athleteId -> rank und name -> rank."""
    idx = http_get(f"https://sports.core.api.espn.com/v2/sports/tennis/leagues/{tour}/rankings")
    by_id, by_name = {}, {}
    if not idx or not idx.get("items"):
        return by_id, by_name
    ref = idx["items"][0].get("$ref", "").replace("http://", "https://")
    doc = http_get(ref)
    if not doc:
        return by_id, by_name
    for entry in doc.get("ranks", []):
        rank = entry.get("current")
        ath_ref = (entry.get("athlete") or {}).get("$ref", "")
        m = re.search(r"/athletes/(\d+)", ath_ref)
        if rank and m:
            by_id[m.group(1)] = rank
        # manche Feeds haben den Namen inline
        nm = (entry.get("athlete") or {}).get("displayName")
        if rank and nm:
            by_name[norm_team(nm)] = rank
    return by_id, by_name


def tennis_predict(rank1, rank2):
    """Einfaches Ranglisten-Modell: P(1 gewinnt)."""
    if not rank1 and not rank2:
        return None
    r1 = float(rank1) if rank1 else 250.0
    r2 = float(rank2) if rank2 else 250.0
    e = 0.85
    p1 = r2 ** e / (r1 ** e + r2 ** e)
    return round(p1, 4)


# ----------------------------------------------------------------------------
# Hauptprogramm
# ----------------------------------------------------------------------------

def main():
    season = current_season_year()
    season_start = datetime(season, 7, 1, tzinfo=TZ)
    years = [season - 1, season]
    out = {
        "generatedAt": NOW.isoformat(),
        "windowDays": DAYS_AHEAD,
        "days": [(TODAY + timedelta(days=i)).isoformat() for i in range(DAYS_AHEAD)],
        "football": [],
        "tennis": [],
        "meta": {"oddsApiEnabled": bool(ODDS_API_KEY), "season": f"{season}/{str(season+1)[2:]}"},
    }

    fixture_odds = load_fixture_odds_fdcuk()
    print(f"fixtures.csv: {len(fixture_odds)} Spiele mit Quoten")

    for lg in LEAGUES:
        print(f"== {lg['name']} ==")
        # 1) Ergebnisse (Form + Modell)
        if lg["source"] == "openligadb":
            results = load_results_openligadb(lg["oldb"], years)
        else:
            results = load_results_fdcuk(lg["fdcuk"], years) if lg["fdcuk"] else []
            if len(results) < 50:
                results.extend(load_results_espn(lg["espn"], years))
        print(f"  {len(results)} Ergebnisse geladen")

        strengths, league_avg, home_adv = build_strengths(results)
        table, n_teams = compute_table(results, season_start)
        season_results = [r for r in results if r["date"] >= season_start]

        # 2) Kommende Spiele
        if lg["source"] == "openligadb":
            upcoming, first_future = upcoming_openligadb(lg["oldb"], season)
        else:
            upcoming, first_future = upcoming_espn(lg["espn"])
        print(f"  {len(upcoming)} Spiele in den naechsten {DAYS_AHEAD} Tagen")

        matches_out = []
        for m in sorted(upcoming, key=lambda x: x["dt"]):
            pred = predict_match(strengths, league_avg, home_adv, m["home"], m["away"])
            odds = find_odds(fixture_odds, lg["fdcuk"], m["home"], m["away"])
            if not odds and ODDS_API_KEY:
                odds = odds_api_football(ODDS_API_SPORT_KEYS.get(lg["id"], ""), m["home"], m["away"])
            value = None
            if odds and pred:
                imp = implied_probs(odds)
                if imp:
                    diffs = [pred["pHome"] - imp[0], pred["pDraw"] - imp[1], pred["pAway"] - imp[2]]
                    best = max(range(3), key=lambda i: diffs[i])
                    if diffs[best] >= 0.05:
                        value = {"outcome": ["1", "X", "2"][best],
                                 "edge": round(diffs[best], 4),
                                 "modelP": [pred["pHome"], pred["pDraw"], pred["pAway"]][best],
                                 "odds": [odds["h"], odds["d"], odds["a"]][best]}
            matches_out.append({
                "kickoff": m["dt"].isoformat(),
                "home": m["home"], "away": m["away"],
                "homeIcon": m.get("homeIcon"), "awayIcon": m.get("awayIcon"),
                "matchday": m.get("matchday"),
                "formHome": team_form(results, m["home"]),
                "formAway": team_form(results, m["away"]),
                "posHome": table_pos(table, m["home"]),
                "posAway": table_pos(table, m["away"]),
                "nTeams": n_teams if n_teams else None,
                "h2h": head_to_head(results, m["home"], m["away"]),
                "prediction": pred,
                "odds": odds,
                "value": value,
            })

        league_out = {
            "id": lg["id"], "name": lg["name"], "flag": lg["flag"],
            "matches": matches_out,
            "seasonHasStarted": len(season_results) > 0,
        }
        if not matches_out and first_future:
            league_out["nextMatch"] = {
                "kickoff": first_future["dt"].isoformat(),
                "home": first_future["home"], "away": first_future["away"],
                "matchday": first_future.get("matchday"),
            }
        out["football"].append(league_out)

    # ---- Tennis ----
    print("== Tennis ==")
    rank_atp_id, rank_atp_nm = espn_rankings("atp")
    rank_wta_id, rank_wta_nm = espn_rankings("wta")
    print(f"  Rankings: ATP {len(rank_atp_id) or len(rank_atp_nm)}, WTA {len(rank_wta_id) or len(rank_wta_nm)}")

    seen = set()
    tennis_out = []
    for i in range(DAYS_AHEAD):
        day = TODAY + timedelta(days=i)
        day_matches = []
        for tour in ("atp", "wta"):
            day_matches.extend(espn_tennis_day(tour, day))
        # TheSportsDB nur als Ergaenzung, wenn ESPN fuer diese Tour an dem Tag
        # nichts liefert. Community-Daten ordnen Turniere teils falsch zu,
        # daher werden solche Eintraege als "unbestaetigt" markiert.
        espn_tours_today = {m["tour"] for m in day_matches}
        for m in tsdb_tennis_day(day):
            if m["tour"] not in espn_tours_today:
                day_matches.append(m)
        for m in day_matches:
            key = (m["tour"], norm_team(m["p1"]["name"]), norm_team(m["p2"]["name"]), m["dt"].date().isoformat())
            key_rev = (m["tour"], key[2], key[1], key[3])
            if key in seen or key_rev in seen:
                continue
            seen.add(key)
            by_id = rank_atp_id if m["tour"] == "ATP" else rank_wta_id
            by_nm = rank_atp_nm if m["tour"] == "ATP" else rank_wta_nm
            r1 = by_id.get(m["p1"]["id"]) or by_nm.get(norm_team(m["p1"]["name"]))
            r2 = by_id.get(m["p2"]["id"]) or by_nm.get(norm_team(m["p2"]["name"]))
            p1win = tennis_predict(r1, r2)
            tennis_out.append({
                "start": m["dt"].isoformat(),
                "tour": m["tour"], "tournament": m["tournament"],
                "round": m.get("round") or "",
                "p1": {"name": m["p1"]["name"], "rank": r1},
                "p2": {"name": m["p2"]["name"], "rank": r2},
                "pP1": p1win,
                "unconfirmed": m.get("src") == "tsdb",
            })
    tennis_out.sort(key=lambda x: x["start"])
    out["tennis"] = tennis_out
    print(f"  {len(tennis_out)} Tennis-Matches in den naechsten {DAYS_AHEAD} Tagen")

    os.makedirs(os.path.join(os.path.dirname(__file__), "..", "data"), exist_ok=True)
    path = os.path.join(os.path.dirname(__file__), "..", "data", "data.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"OK -> {path}")


if __name__ == "__main__":
    main()
