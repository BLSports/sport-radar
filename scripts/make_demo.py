#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Erzeugt data/demo_data.json: Demo-Spieltag (echte Ansetzungen des 1. Spieltags 2026/27,
Beispiel-Staerken -> Modell rechnet echte Wahrscheinlichkeiten). Klar als Demo gekennzeichnet."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from fetch_data import poisson_probs  # noqa: E402

# (Heim, Gast, Anstoss, Staerke Heim (att, def), Staerke Gast, Form H, Form A, Pos H, Pos A, Quoten)
DEMO = [
    ("FC Bayern München", "VfB Stuttgart", "2026-08-28T20:30:00+02:00",
     (1.65, 0.72), (1.15, 0.95), "SSSUS", "SNSSU", 1, 5, (1.42, 5.10, 6.60)),
    ("Borussia Dortmund", "Hamburger SV", "2026-08-29T15:30:00+02:00",
     (1.35, 0.85), (0.90, 1.10), "SUSSN", "USNSS", 3, 12, (1.55, 4.40, 5.80)),
    ("RB Leipzig", "Borussia Mönchengladbach", "2026-08-29T15:30:00+02:00",
     (1.30, 0.80), (1.05, 1.05), "SSNUS", "NUSUN", 4, 9, (1.75, 4.00, 4.40)),
    ("SC Freiburg", "SV Werder Bremen", "2026-08-29T15:30:00+02:00",
     (1.05, 0.95), (1.00, 1.10), "USSNU", "SNUNS", 7, 10, (2.10, 3.55, 3.45)),
    ("1. FC Union Berlin", "Eintracht Frankfurt", "2026-08-29T15:30:00+02:00",
     (0.90, 1.00), (1.20, 0.95), "NUSUN", "SUSSN", 13, 6, (3.30, 3.40, 2.20)),
    ("SV 07 Elversberg", "Bayer 04 Leverkusen", "2026-08-29T15:30:00+02:00",
     (0.85, 1.15), (1.45, 0.80), "SUNSU", "SSUSS", 15, 2, (5.20, 4.20, 1.62)),
]

LEAGUE_AVG = 1.55
HOME_ADV = 1.18


def predict(sh, sa):
    mu_h = LEAGUE_AVG * sh[0] * sa[1] * HOME_ADV
    mu_a = LEAGUE_AVG * sa[0] * sh[1] / HOME_ADV
    p_h, p_d, p_a, p_o25, score = poisson_probs(mu_h, mu_a)
    return {
        "pHome": round(p_h, 4), "pDraw": round(p_d, 4), "pAway": round(p_a, 4),
        "pOver25": round(p_o25, 4), "xgHome": round(mu_h, 2), "xgAway": round(mu_a, 2),
        "tipScore": f"{score[0]}:{score[1]}", "confidence": "hoch",
    }


def main():
    matches = []
    for home, away, ko, sh, sa, fh, fa, ph, pa, odds in DEMO:
        pred = predict(sh, sa)
        o = {"h": odds[0], "d": odds[1], "a": odds[2], "src": "Beispiel"}
        inv = [1 / x for x in odds]
        s = sum(inv)
        imp = [x / s for x in inv]
        diffs = [pred["pHome"] - imp[0], pred["pDraw"] - imp[1], pred["pAway"] - imp[2]]
        best = max(range(3), key=lambda i: diffs[i])
        value = None
        if diffs[best] >= 0.05:
            value = {"outcome": ["1", "X", "2"][best], "edge": round(diffs[best], 4),
                     "modelP": [pred["pHome"], pred["pDraw"], pred["pAway"]][best],
                     "odds": odds[best]}
        matches.append({
            "kickoff": ko, "home": home, "away": away, "homeIcon": None, "awayIcon": None,
            "matchday": 1, "formHome": list(fh), "formAway": list(fa),
            "posHome": ph, "posAway": pa, "nTeams": 18, "h2h": [],
            "prediction": pred, "odds": o, "value": value,
        })

    out = {
        "generatedAt": "2026-08-28T07:00:00+02:00",
        "windowDays": 3,
        "days": ["2026-08-28", "2026-08-29", "2026-08-30"],
        "football": [
            {"id": "bl1", "name": "1. Bundesliga", "flag": "\U0001F1E9\U0001F1EA",
             "matches": matches, "seasonHasStarted": True},
        ],
        "tennis": [
            {"start": "2026-08-29T13:00:00+02:00", "tour": "ATP", "tournament": "Beispiel-Turnier",
             "round": "Halbfinale", "p1": {"name": "Spieler A", "rank": 8},
             "p2": {"name": "Spieler B", "rank": 31}, "pP1": 0.76},
        ],
        "meta": {"oddsApiEnabled": False, "season": "2026/27", "demo": True},
    }
    path = os.path.join(os.path.dirname(__file__), "..", "data", "demo_data.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"OK -> {path}")


if __name__ == "__main__":
    main()
