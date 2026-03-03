import json
import math
import random
import os
import re
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from difflib import get_close_matches
from collections import Counter
from itertools import permutations, combinations

SIMULACIONES = 50000
FACTOR_LOCALIA = 1.12
ARCHIVO_HISTORIAL = "historial_partidos.json"
BESOCCER_BASE_URL = "https://es.besoccer.com"

ALIAS = {
    "barca": "barcelona",
    "fc barcelona": "barcelona",
    "barça": "barcelona",
    "fcb": "barcelona",
    "bcn": "barcelona",
    "barcelona fc": "barcelona",
    "real madrid": "real madrid",
    "rm": "real madrid",
    "rma": "real madrid",
    "real": "real madrid",
    "madrid cf": "real madrid",
    "los blancos": "real madrid",
    "atleti": "atletico madrid",
    "atletico": "atletico madrid",
    "atm": "atletico madrid",
    "atletico de madrid": "atletico madrid",
    "colchoneros": "atletico madrid",
    "sevilla fc": "sevilla",
    "sev": "sevilla",
    "valencia cf": "valencia",
    "val": "valencia",
    "real sociedad": "real sociedad",
    "la real": "real sociedad",
    "betis": "real betis",
    "real betis balompie": "real betis",
    "villarreal cf": "villarreal",
    "submarino amarillo": "villarreal",
    "athletic": "athletic club",
    "athletic bilbao": "athletic club",
    "manchester city": "man city",
    "mancity": "man city",
    "manchester city fc": "man city",
    "mcfc": "man city",
    "citizens": "man city",
    "city": "man city",
    "manchester united": "man united",
    "man utd": "man united",
    "mufc": "man united",
    "manchester united fc": "man united",
    "red devils": "man united",
    "united": "man united",
    "manchester": "man united",
    "liverpool fc": "liverpool",
    "lfc": "liverpool",
    "reds": "liverpool",
    "chelsea fc": "chelsea",
    "cfc": "chelsea",
    "blues": "chelsea",
    "arsenal fc": "arsenal",
    "afc": "arsenal",
    "gunners": "arsenal",
    "tottenham": "tottenham hotspur",
    "spurs": "tottenham hotspur",
    "tottenham hotspur fc": "tottenham hotspur",
    "newcastle": "newcastle united",
    "newcastle united fc": "newcastle united",
    "aston villa fc": "aston villa",
    "bayern": "bayern munchen",
    "bayern munich": "bayern munchen",
    "fcbayern": "bayern munchen",
    "fc bayern": "bayern munchen",
    "dortmund": "borussia dortmund",
    "bvb": "borussia dortmund",
    "borussia": "borussia dortmund",
    "rb leipzig": "rb leipzig",
    "leipzig": "rb leipzig",
    "bayer leverkusen": "bayer leverkusen",
    "leverkusen": "bayer leverkusen",
    "milan": "ac milan",
    "acmilan": "ac milan",
    "rossoneri": "ac milan",
    "inter": "inter milan",
    "internazionale": "inter milan",
    "inter milano": "inter milan",
    "nerazzurri": "inter milan",
    "juve": "juventus",
    "juventus fc": "juventus",
    "juventus turin": "juventus",
    "roma": "as roma",
    "as roma": "as roma",
    "lazio": "lazio",
    "napoli": "napoli",
    "ssc napoli": "napoli",
    "psg": "paris saint-germain",
    "paris sg": "paris saint-germain",
    "paris saint germain": "paris saint-germain",
    "marseille": "olympique de marseille",
    "om": "olympique de marseille",
    "lyon": "olympique lyonnais",
    "ol": "olympique lyonnais",
    "monaco": "as monaco",
    "asm": "as monaco",
    "river": "river plate",
    "river plate": "river plate",
    "carp": "river plate",
    "millonarios": "river plate",
    "padre de boca": "river plate",
    "el mas grandre": "river plate",
    "boca": "boca juniors",
    "boca juniors": "boca juniors",
    "cabj": "boca juniors",
    "xeneize": "boca juniors",
    "independiente": "independiente",
    "ca independiente": "independiente",
    "rojo": "independiente",
    "racing": "racing club",
    "racing club avellaneda": "racing club",
    "san lorenzo": "san lorenzo",
    "ciclón": "san lorenzo",
    "estudiantes": "estudiantes de la plata",
    "pincha": "estudiantes de la plata",
    "velez": "velez sarsfield",
    "fortin": "velez sarsfield",
    "flamengo": "flamengo",
    "mengao": "flamengo",
    "palmeiras": "palmeiras",
    "corinthians": "corinthians",
    "timao": "corinthians",
    "santos": "santos",
    "sao paulo": "sao paulo",
    "spfc": "sao paulo"
}

MANUAL_TEAM_STATUS = {
    # "real madrid": {"injuries_impact": 0.08}
}

# Cada módulo es independiente y puede activarse/desactivarse para testear su impacto.
MODULE_FLAGS = {
    "league_calibration": True,
    "overperformance_detector": True,
    "fatigue_schedule": True,
    "draw_calibration": True,
    "favorite_fragility": True,
    "matchup_style": True,
    "context_motivation": True,
    "early_impact": True,
    "market_gap": True,
    "dynamic_confidence": True,
}

DEFAULT_LEAGUE_PROFILE = {
    "draw_rate": 0.27,
    "goal_variance": 1.35,
    "home_advantage": FACTOR_LOCALIA,
    "xg_mean": 1.30,
}

LEAGUE_CALIBRATION = {}
TEAM_MATCH_CACHE = {}


COMPETITION_LEAGUE_HINTS = {
    "premier": "premier_league",
    "eng (europa)": "premier_league",
    "bundesliga": "bundesliga",
    "ger (europa)": "bundesliga",
    "ligue 1": "ligue_1",
    "fra (europa)": "ligue_1",
}


def modulo_activo(nombre):
    return MODULE_FLAGS.get(nombre, False)


def identificar_liga(equipo_local, equipo_visitante=None):
    claves = []
    for equipo in [equipo_local, equipo_visitante]:
        if not equipo:
            continue
        liga = str(equipo.get("liga", "")).lower()
        claves.append(liga)

    for liga in claves:
        for hint, canonical in COMPETITION_LEAGUE_HINTS.items():
            if hint in liga:
                return canonical
    return "default"


def _extraer_xg_texto(texto):
    patron = re.search(r"xg\s*[:=]?\s*(\d+[\.,]?\d*)\s*[-:]\s*(\d+[\.,]?\d*)", texto, flags=re.I)
    if not patron:
        return None, None
    return float(patron.group(1).replace(",", ".")), float(patron.group(2).replace(",", "."))


def _team_recent_matches(equipo, limit=12):
    nombre = equipo["nombre"]
    if nombre in TEAM_MATCH_CACHE:
        return TEAM_MATCH_CACHE[nombre][:limit]
    try:
        partidos = _parsear_partidos_besoccer(nombre)
    except Exception:
        partidos = []

    objetivo = normalizar_nombre(nombre)
    data = []
    for p in partidos:
        is_home = normalizar_nombre(p["home"]) == objetivo
        is_away = normalizar_nombre(p["away"]) == objetivo
        if not (is_home or is_away):
            continue

        gf, ga = (p["gh"], p["ga"]) if is_home else (p["ga"], p["gh"])
        xg_h, xg_a = _extraer_xg_texto(p.get("competition", ""))
        xg_for = None
        xga = None
        if xg_h is not None and xg_a is not None:
            xg_for, xga = (xg_h, xg_a) if is_home else (xg_a, xg_h)

        data.append({
            "gf": gf,
            "ga": ga,
            "xg_for": xg_for,
            "xga": xga,
            "datetime": p.get("datetime"),
            "competition": p.get("competition", ""),
            "is_home": is_home,
        })

    TEAM_MATCH_CACHE[nombre] = data
    return data[:limit]


def calibrar_ligas(db):
    league_buckets = {"premier_league": [], "bundesliga": [], "ligue_1": []}
    for equipo in db.values():
        key = identificar_liga(equipo)
        if key in league_buckets:
            league_buckets[key].append(equipo)

    output = {}
    for league_key, equipos in league_buckets.items():
        goles_totales, total_matches = [], 0
        draw_count, home_wins = 0, 0
        xg_vals = []
        for equipo in equipos[:8]:
            for m in _team_recent_matches(equipo, limit=10):
                if not m["is_home"]:
                    continue
                total_matches += 1
                goles_totales.append(m["gf"] + m["ga"])
                if m["gf"] == m["ga"]:
                    draw_count += 1
                if m["gf"] > m["ga"]:
                    home_wins += 1
                if m["xg_for"] is not None:
                    xg_vals.append(m["xg_for"])

        if total_matches < 8:
            output[league_key] = DEFAULT_LEAGUE_PROFILE.copy()
            continue

        mean_goals = sum(goles_totales) / len(goles_totales)
        variance = sum((g - mean_goals) ** 2 for g in goles_totales) / max(1, len(goles_totales))
        output[league_key] = {
            "draw_rate": max(0.18, min(0.40, draw_count / total_matches)),
            "goal_variance": max(0.9, min(2.2, variance)),
            "home_advantage": max(1.05, min(1.25, 1.0 + ((home_wins / total_matches) - 0.40) * 0.35)),
            "xg_mean": max(0.9, min(2.0, (sum(xg_vals) / len(xg_vals)) if xg_vals else DEFAULT_LEAGUE_PROFILE["xg_mean"])),
        }

    output["default"] = DEFAULT_LEAGUE_PROFILE.copy()
    return output


def perfil_liga(local, visita):
    if not modulo_activo("league_calibration"):
        return DEFAULT_LEAGUE_PROFILE.copy(), "default"
    league_key = identificar_liga(local, visita)
    return LEAGUE_CALIBRATION.get(league_key, DEFAULT_LEAGUE_PROFILE.copy()), league_key


def calcular_opi(equipo):
    if not modulo_activo("overperformance_detector"):
        return {"opi": 0.0, "alerta": False, "factor": 1.0}

    muestra = _team_recent_matches(equipo, limit=10)
    if not muestra:
        return {"opi": 0.0, "alerta": False, "factor": 1.0}

    gf = sum(x["gf"] for x in muestra)
    ga = sum(x["ga"] for x in muestra)
    xg_for_vals = [x["xg_for"] for x in muestra if x["xg_for"] is not None]
    xga_vals = [x["xga"] for x in muestra if x["xga"] is not None]
    xg_for = sum(xg_for_vals) if xg_for_vals else gf
    xga = sum(xga_vals) if xga_vals else ga

    opi_attack = (gf - xg_for) / max(1.0, len(muestra))
    opi_def = (xga - ga) / max(1.0, len(muestra))
    opi = max(-1.5, min(1.5, (opi_attack + opi_def) / 2))
    penal = max(0.0, opi) * 0.035
    factor = max(0.94, min(1.01, 1.0 - penal))

    return {"opi": opi, "alerta": opi > 0.30, "factor": factor}


def calcular_fatigue_index(carga):
    if not modulo_activo("fatigue_schedule"):
        return {"fi": 0.0, "factor": 1.0}
    fi = 0.0
    fi += min(0.55, carga["partidos_14d"] * 0.11)
    if carga["dias_descanso"] <= 3:
        fi += 0.2
    if carga["jugo_internacional"]:
        fi += 0.18
    if carga["extra_time_reciente"]:
        fi += 0.12
    fi = min(1.0, fi)
    factor = max(0.92, min(1.02, 1.0 - (fi * 0.05)))
    return {"fi": fi, "factor": factor}


def calcular_draw_likelihood_score(local, visita, contexto):
    if not modulo_activo("draw_calibration"):
        return {"dls": 0, "factores": 0, "boost": 0.0}

    factores = 0
    off_balance = abs((local["ataque"] + local["mediocampo"]) - (visita["ataque"] + visita["mediocampo"]))
    if off_balance <= 8:
        factores += 1

    xg_diff = abs(contexto["xg_base_local"] - contexto["xg_base_visitante"])
    if xg_diff <= 0.22:
        factores += 1

    under_tend = contexto["xg_base_local"] + contexto["xg_base_visitante"] <= 2.55
    if under_tend:
        factores += 1

    quality_gap = abs(local["elo"] - visita["elo"])
    if quality_gap <= 60:
        factores += 1

    pace = (local["ataque"] + visita["ataque"]) / 2
    if pace <= 83:
        factores += 1

    dls = factores / 5
    boost = 0.0
    if factores >= 3:
        boost = min(0.055, 0.018 + (factores - 3) * 0.012)
    return {"dls": dls, "factores": factores, "boost": boost}


def calcular_fragility_index(favorito):
    if not modulo_activo("favorite_fragility"):
        return {"ffi": 0.0, "factor": 1.0, "alerta": False}

    muestra = _team_recent_matches(favorito, limit=12)
    if not muestra:
        return {"ffi": 0.0, "factor": 1.0, "alerta": False}

    min_margin_wins = sum(1 for m in muestra if m["gf"] > m["ga"] and (m["gf"] - m["ga"]) == 1)
    xga_high = sum(1 for m in muestra if (m["xga"] or m["ga"]) >= 1.5)
    conceded = sum(m["ga"] for m in muestra) / len(muestra)

    ffi = (min_margin_wins / len(muestra)) * 0.45 + (xga_high / len(muestra)) * 0.35 + min(0.2, conceded / 10)
    ffi = min(1.0, ffi)
    factor = max(0.93, min(1.0, 1 - ffi * 0.06))
    return {"ffi": ffi, "factor": factor, "alerta": ffi > 0.55}


def calcular_matchup_style_factor(local, visita):
    if not modulo_activo("matchup_style"):
        return {"msf_local": 1.0, "msf_visitante": 1.0, "perfil": "neutral"}

    local_style = "defensivo" if local["defensa"] - local["ataque"] >= 8 else "propositivo"
    visita_style = "defensivo" if visita["defensa"] - visita["ataque"] >= 8 else "propositivo"

    if local_style == "propositivo" and visita_style == "defensivo":
        return {"msf_local": 0.985, "msf_visitante": 1.01, "perfil": "bloque_bajo_vs_posesion"}
    if local_style == "defensivo" and visita_style == "propositivo":
        return {"msf_local": 1.01, "msf_visitante": 0.985, "perfil": "contraataque"}
    return {"msf_local": 1.0, "msf_visitante": 1.0, "perfil": "parejo"}


def calcular_context_motivation_index(local, visita, contexto):
    if not modulo_activo("context_motivation"):
        return {"cmi_local": 1.0, "cmi_visitante": 1.0}

    cmi_local, cmi_visitante = 1.0, 1.0
    if contexto["carga_local"]["jugo_internacional"] and contexto["carga_local"]["dias_descanso"] <= 3:
        cmi_local -= 0.01
    if contexto["carga_visitante"]["jugo_internacional"] and contexto["carga_visitante"]["dias_descanso"] <= 3:
        cmi_visitante -= 0.01

    if abs(local["elo"] - visita["elo"]) > 180:
        if local["elo"] > visita["elo"]:
            cmi_local -= 0.004
            cmi_visitante += 0.004
        else:
            cmi_visitante -= 0.004
            cmi_local += 0.004

    return {"cmi_local": max(0.97, cmi_local), "cmi_visitante": max(0.97, cmi_visitante)}


def calcular_early_impact_index(local, visita):
    if not modulo_activo("early_impact"):
        return {"eii_local": 1.0, "eii_visitante": 1.0}

    momentum_local = (local["ataque"] + local["forma"] * 35) / max(1, local["defensa"])
    momentum_visit = (visita["ataque"] + visita["forma"] * 35) / max(1, visita["defensa"])
    diff = max(-0.08, min(0.08, (momentum_local - momentum_visit) * 0.03))
    return {"eii_local": 1 + diff, "eii_visitante": 1 - diff}


def calcular_market_gap(local, visita, probs):
    if not modulo_activo("market_gap"):
        return {"mmg": 0.0, "alerta": False}

    odds_l = local.get("odds_win")
    odds_v = visita.get("odds_win")
    if not odds_l or not odds_v:
        return {"mmg": 0.0, "alerta": False}

    market_home = 1 / odds_l
    model_home = probs["L"]
    mmg = abs(market_home - model_home)
    return {"mmg": mmg, "alerta": mmg >= 0.12}


def clasificar_confianza(probs, contexto):
    if not modulo_activo("dynamic_confidence"):
        return {"nivel": "media", "score": 0.5}

    top = max(probs.values())
    second = sorted(probs.values(), reverse=True)[1]
    spread = top - second
    contradiccion = 0.0
    contradiccion += max(0, contexto["opi_local"]["opi"]) * 0.08
    contradiccion += max(0, contexto["opi_visitante"]["opi"]) * 0.08
    contradiccion += contexto["fragility"]["ffi"] * 0.1
    contradiccion = min(0.4, contradiccion)

    score = max(0.0, min(1.0, (spread * 2.1) + 0.35 - contradiccion))
    if score >= 0.66:
        nivel = "alta"
    elif score >= 0.45:
        nivel = "media"
    else:
        nivel = "baja"
    return {"nivel": nivel, "score": score}


def cargar_db():
    if not os.path.exists("equipos.json"):
        print("❌ No existe equipos.json. Ejecuta primero actualizar_db.py")
        return None
    with open("equipos.json", "r", encoding="utf-8") as f:
        return json.load(f)


def cargar_historial():
    if not os.path.exists(ARCHIVO_HISTORIAL):
        return []
    with open(ARCHIVO_HISTORIAL, "r", encoding="utf-8") as f:
        return json.load(f)


def guardar_historial(registro):
    historial = cargar_historial()
    historial.append(registro)
    with open(ARCHIVO_HISTORIAL, "w", encoding="utf-8") as f:
        json.dump(historial, f, indent=4, ensure_ascii=False)


def normalizar_nombre(texto):
    limpio = re.sub(r"[^a-z0-9áéíóúñü\s-]", "", texto.lower()).strip()
    limpio = re.sub(r"\s+", " ", limpio)
    return ALIAS.get(limpio, limpio)


def buscar_equipo(nombre_usuario, db):
    nombre_limpio = normalizar_nombre(nombre_usuario)
    if nombre_limpio in db:
        return nombre_limpio

    coincidencias = get_close_matches(nombre_limpio, db.keys(), n=3, cutoff=0.6)
    if coincidencias:
        print(f"\n🤔 No encontré '{nombre_usuario}'. ¿Tal vez?")
        for i, pos in enumerate(coincidencias):
            print(f"  {i+1}. {db[pos]['nombre']}")
        rta = input("Selecciona número o Enter para cancelar: ")
        if rta.isdigit() and 1 <= int(rta) <= len(coincidencias):
            return coincidencias[int(rta) - 1]
    return None


def _slugify(nombre):
    nombre = normalizar_nombre(nombre)
    nombre = nombre.replace(" ", "-")
    nombre = nombre.replace("ñ", "n")
    nombre = re.sub(r"[^a-z0-9-]", "", nombre)
    return nombre


def _http_get(url):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _resolver_url_partidos(equipo_nombre):
    nombre_query = urllib.parse.quote(equipo_nombre)
    try:
        search_html = _http_get(f"{BESOCCER_BASE_URL}/busqueda/equipo?q={nombre_query}")
        soup = BeautifulSoup(search_html, "html.parser")
        enlace_equipo = soup.find("a", href=re.compile(r"^/equipo/"))
        if enlace_equipo and enlace_equipo.get("href"):
            href = enlace_equipo["href"].split("?")[0].rstrip("/")
            return f"{BESOCCER_BASE_URL}{href.replace('/equipo/', '/equipo/partidos/', 1)}"
    except Exception:
        pass

    return f"{BESOCCER_BASE_URL}/equipo/partidos/{_slugify(equipo_nombre)}"


def _parsear_partidos_besoccer(equipo_nombre):
    url = _resolver_url_partidos(equipo_nombre)
    html = _http_get(url)
    soup = BeautifulSoup(html, "html.parser")
    partidos = []

    for nodo in soup.find_all(["tr", "article", "div"], class_=re.compile(r"match|panel-body|item", re.I)):
        texto = nodo.get_text(" ", strip=True)
        score_match = re.search(r"(\d+)\s*[-:]\s*(\d+)", texto)
        if not score_match:
            continue

        nombres = [n.get_text(" ", strip=True) for n in nodo.select(".team-name, .name")]
        if len(nombres) < 2:
            candidato = re.findall(r"([A-Za-zÁÉÍÓÚÑÜáéíóúñü\-. ]{3,})", texto)
            nombres = [x.strip() for x in candidato if len(x.strip().split()) <= 5]
            if len(nombres) < 2:
                continue

        home_team, away_team = nombres[0], nombres[1]
        gl, gv = int(score_match.group(1)), int(score_match.group(2))

        dt = None
        time_tag = nodo.find("time")
        if time_tag and time_tag.get("datetime"):
            raw_dt = time_tag.get("datetime")
            try:
                dt = datetime.fromisoformat(raw_dt.replace("Z", "+00:00"))
            except ValueError:
                dt = None

        meta = texto.lower()
        partidos.append(
            {
                "home": home_team,
                "away": away_team,
                "gh": gl,
                "ga": gv,
                "datetime": dt,
                "competition": meta,
            }
        )

    return partidos


def obtener_invicto_local_real(equipo):
    """Devuelve la racha vigente de partidos invicto en casa de forma consecutiva."""
    try:
        partidos = _parsear_partidos_besoccer(equipo["nombre"])
        if not partidos:
            return 0

        objetivo = normalizar_nombre(equipo["nombre"])
        racha = 0
        for partido in partidos:
            if normalizar_nombre(partido["home"]) != objetivo:
                continue
            if partido["gh"] >= partido["ga"]:
                racha += 1
            else:
                break
        return min(racha, 25)
    except Exception:
        return 0


def calcular_boost_fortin(invicto_local):
    """Calcula un boost leve y progresivo por invicto local real."""
    if invicto_local <= 5:
        return 1.0
    if invicto_local <= 8:
        return 1.012
    if invicto_local <= 12:
        return 1.022
    return 1.032


def _resolver_elo_rival(nombre_rival, db):
    clave = normalizar_nombre(nombre_rival)
    if clave in db:
        return db[clave]["elo"]
    coincidencias = get_close_matches(clave, db.keys(), n=1, cutoff=0.86)
    if coincidencias:
        return db[coincidencias[0]]["elo"]
    return 1500


def calcular_forma_real(equipo, db, ultimos=5):
    """Extrae forma contextual real en últimos partidos jugados."""
    try:
        partidos = _parsear_partidos_besoccer(equipo["nombre"])
    except Exception:
        return {
            "partidos": 0,
            "puntos": 0,
            "gf": 0,
            "gc": 0,
            "dg": 0,
            "opponent_quality": 1500,
            "factor": 1.0,
        }

    objetivo = normalizar_nombre(equipo["nombre"])
    muestra = []
    for p in partidos:
        is_home = normalizar_nombre(p["home"]) == objetivo
        is_away = normalizar_nombre(p["away"]) == objetivo
        if not (is_home or is_away):
            continue

        gf, gc = (p["gh"], p["ga"]) if is_home else (p["ga"], p["gh"])
        rival = p["away"] if is_home else p["home"]
        calidad_rival = _resolver_elo_rival(rival, db)

        if gf > gc:
            pts = 3
        elif gf == gc:
            pts = 1
        else:
            pts = 0
        muestra.append({"pts": pts, "gf": gf, "gc": gc, "elo_rival": calidad_rival})
        if len(muestra) >= ultimos:
            break

    if not muestra:
        return {
            "partidos": 0,
            "puntos": 0,
            "gf": 0,
            "gc": 0,
            "dg": 0,
            "opponent_quality": 1500,
            "factor": 1.0,
        }

    puntos = sum(x["pts"] for x in muestra)
    gf = sum(x["gf"] for x in muestra)
    gc = sum(x["gc"] for x in muestra)
    dg = gf - gc
    calidad = sum(x["elo_rival"] for x in muestra) / len(muestra)

    forma_ppg = puntos / (3 * len(muestra))
    ajuste_dg = max(-0.05, min(0.05, dg * 0.01))
    ajuste_calidad = max(-0.03, min(0.03, (calidad - 1500) / 4000))
    factor = 0.95 + (forma_ppg * 0.1) + ajuste_dg + ajuste_calidad
    factor = max(0.90, min(1.08, factor))

    return {
        "partidos": len(muestra),
        "puntos": puntos,
        "gf": gf,
        "gc": gc,
        "dg": dg,
        "opponent_quality": calidad,
        "factor": factor,
    }


def calcular_carga_fisica_y_descanso(equipo):
    """Analiza carga de partidos, descanso y posibles señales de desgaste."""
    try:
        partidos = _parsear_partidos_besoccer(equipo["nombre"])
    except Exception:
        return {
            "partidos_14d": 0,
            "dias_descanso": 7,
            "jugo_internacional": False,
            "extra_time_reciente": False,
            "factor_carga": 1.0,
        }

    objetivo = normalizar_nombre(equipo["nombre"])
    ahora = datetime.now(timezone.utc)
    propios = [
        p for p in partidos
        if normalizar_nombre(p["home"]) == objetivo or normalizar_nombre(p["away"]) == objetivo
    ]

    if not propios:
        return {
            "partidos_14d": 0,
            "dias_descanso": 7,
            "jugo_internacional": False,
            "extra_time_reciente": False,
            "factor_carga": 1.0,
        }

    recientes_con_fecha = [p for p in propios if p["datetime"] is not None]
    partidos_14d = 0
    dias_descanso = 7
    if recientes_con_fecha:
        for p in recientes_con_fecha:
            diff_dias = (ahora - p["datetime"].astimezone(timezone.utc)).days
            if 0 <= diff_dias <= 14:
                partidos_14d += 1
        dias_descanso = max(0, (ahora - recientes_con_fecha[0]["datetime"].astimezone(timezone.utc)).days)

    jugo_internacional = any(
        any(k in p["competition"] for k in ["champions", "europa", "libertadores", "sudamericana", "conference"])
        for p in propios[:6]
    )
    extra_time_reciente = any(any(k in p["competition"] for k in ["prórroga", "penaltis", "tiempo extra"]) for p in propios[:6])

    carga_penal = min(0.05, partidos_14d * 0.012)
    inter_penal = 0.012 if jugo_internacional else 0
    extra_penal = 0.01 if extra_time_reciente else 0
    factor_carga = 1.0 - carga_penal - inter_penal - extra_penal
    factor_carga = max(0.90, min(1.02, factor_carga))

    return {
        "partidos_14d": partidos_14d,
        "dias_descanso": dias_descanso,
        "jugo_internacional": jugo_internacional,
        "extra_time_reciente": extra_time_reciente,
        "factor_carga": factor_carga,
    }


def calcular_ajuste_lesiones(equipo):
    """Sistema modular para incorporar impacto de bajas manuales sin romper el flujo."""
    clave = normalizar_nombre(equipo["nombre"])
    impacto = MANUAL_TEAM_STATUS.get(clave, {}).get("injuries_impact", 0.0)
    impacto = max(0.0, min(0.12, impacto))
    return 1.0 - impacto


def calcular_memoria_historica(nombre_l, nombre_v):
    historial = cargar_historial()
    vl, vv, empates = 0, 0, 0

    for p in historial:
        if p["local"] == nombre_l and p["visitante"] == nombre_v:
            if p["goles_local"] > p["goles_visitante"]:
                vl += 1
            elif p["goles_local"] < p["goles_visitante"]:
                vv += 1
            else:
                empates += 1
        elif p["local"] == nombre_v and p["visitante"] == nombre_l:
            if p["goles_local"] < p["goles_visitante"]:
                vl += 1
            elif p["goles_local"] > p["goles_visitante"]:
                vv += 1
            else:
                empates += 1

    bono_l = 1.0 + (vl * 0.02) + (empates * 0.01)
    bono_v = 1.0 + (vv * 0.02) + (empates * 0.01)

    return bono_l, bono_v, vl, vv, empates


def poisson(lmbda):
    L = math.exp(-lmbda)
    k, p = 0, 1.0
    while p > L:
        k += 1
        p *= random.random()
    return k - 1


def calcular_shock_index(local, visita, res, contexto):
    """Índice auxiliar de potencial sorpresa sin reemplazar la predicción principal."""
    inferior = "V" if local["elo"] >= visita["elo"] else "L"
    superior = "L" if inferior == "V" else "V"

    elo_gap = abs(local["elo"] - visita["elo"])
    elo_term = min(0.28, elo_gap / 2200)

    forma_inf = contexto["forma_visitante"]["factor"] if inferior == "V" else contexto["forma_local"]["factor"]
    forma_sup = contexto["forma_local"]["factor"] if superior == "L" else contexto["forma_visitante"]["factor"]
    forma_term = max(0.0, min(0.22, (forma_inf - forma_sup) * 0.9))

    descanso_inf = contexto["carga_visitante"]["dias_descanso"] if inferior == "V" else contexto["carga_local"]["dias_descanso"]
    descanso_sup = contexto["carga_local"]["dias_descanso"] if superior == "L" else contexto["carga_visitante"]["dias_descanso"]
    descanso_term = max(0.0, min(0.12, (descanso_inf - descanso_sup) * 0.015))

    prob_inferior = res[inferior] / SIMULACIONES
    confianza_modelo = res[superior] / SIMULACIONES
    exceso_confianza_term = max(0.0, min(0.18, (confianza_modelo - 0.58) * 0.55))

    shock = 0.04 + elo_term + forma_term + descanso_term + exceso_confianza_term + (prob_inferior * 0.35)
    shock = max(0.02, min(0.65, shock))
    return shock


def construir_contexto_partido(local, visita, db):
    invicto_local = obtener_invicto_local_real(local)
    forma_local = calcular_forma_real(local, db)
    forma_visitante = calcular_forma_real(visita, db)
    carga_local = calcular_carga_fisica_y_descanso(local)
    carga_visitante = calcular_carga_fisica_y_descanso(visita)

    diff_descanso = carga_local["dias_descanso"] - carga_visitante["dias_descanso"]
    ajuste_descanso_local = max(0.97, min(1.03, 1 + (diff_descanso * 0.004)))

    league_profile, league_key = perfil_liga(local, visita)
    fatigue_local = calcular_fatigue_index(carga_local)
    fatigue_visitante = calcular_fatigue_index(carga_visitante)
    opi_local = calcular_opi(local)
    opi_visitante = calcular_opi(visita)
    style_factor = calcular_matchup_style_factor(local, visita)
    early_impact = calcular_early_impact_index(local, visita)

    xg_base_local = ((local["ataque"] * 0.6 + local["mediocampo"] * 0.4) / 100) * league_profile["xg_mean"]
    xg_base_visitante = ((visita["ataque"] * 0.6 + visita["mediocampo"] * 0.4) / 100) * league_profile["xg_mean"]

    contexto = {
        "league_key": league_key,
        "league_profile": league_profile,
        "invicto_local": invicto_local,
        "boost_fortin": calcular_boost_fortin(invicto_local),
        "forma_local": forma_local,
        "forma_visitante": forma_visitante,
        "carga_local": carga_local,
        "carga_visitante": carga_visitante,
        "fatigue_local": fatigue_local,
        "fatigue_visitante": fatigue_visitante,
        "opi_local": opi_local,
        "opi_visitante": opi_visitante,
        "style_factor": style_factor,
        "early_impact": early_impact,
        "xg_base_local": xg_base_local,
        "xg_base_visitante": xg_base_visitante,
        "ajuste_lesiones_local": calcular_ajuste_lesiones(local),
        "ajuste_lesiones_visitante": calcular_ajuste_lesiones(visita),
        "ajuste_descanso_local": ajuste_descanso_local,
        "ajuste_descanso_visitante": 2 - ajuste_descanso_local,
    }
    contexto["draw_module"] = calcular_draw_likelihood_score(local, visita, contexto)

    favorito = local if local["elo"] >= visita["elo"] else visita
    contexto["fragility"] = calcular_fragility_index(favorito)
    contexto["motivation"] = calcular_context_motivation_index(local, visita, contexto)
    return contexto


def ejecutar_simulacion(local, visita, sims, contexto):
    dif_elo = local["elo"] - visita["elo"]
    bono_jerarquia = 1 + (dif_elo / 1200)
    dif_med = local["mediocampo"] - visita["mediocampo"]
    influencia_med = 1 + (dif_med * 0.008)

    bono_mem_l, bono_mem_v, vl, vv, e = calcular_memoria_historica(local["nombre"], visita["nombre"])
    league_home_adv = contexto["league_profile"]["home_advantage"] if modulo_activo("league_calibration") else FACTOR_LOCALIA

    lambda_L = (
        ((local["ataque"] * 0.6 + local["mediocampo"] * 0.4) / (visita["defensa"] * 0.8 + 20))
        * league_home_adv
        * local["forma"]
        * bono_jerarquia
        * influencia_med
        * contexto["boost_fortin"]
        * bono_mem_l
        * contexto["forma_local"]["factor"]
        * contexto["carga_local"]["factor_carga"]
        * contexto["fatigue_local"]["factor"]
        * contexto["opi_local"]["factor"]
        * contexto["style_factor"]["msf_local"]
        * contexto["motivation"]["cmi_local"]
        * contexto["early_impact"]["eii_local"]
        * contexto["ajuste_descanso_local"]
        * contexto["ajuste_lesiones_local"]
    )

    lambda_V = (
        ((visita["ataque"] * 0.6 + visita["mediocampo"] * 0.4) / (local["defensa"] * 0.8 + 20))
        * visita["forma"]
        / (bono_jerarquia if bono_jerarquia != 0 else 1)
        / influencia_med
        * bono_mem_v
        * contexto["forma_visitante"]["factor"]
        * contexto["carga_visitante"]["factor_carga"]
        * contexto["fatigue_visitante"]["factor"]
        * contexto["opi_visitante"]["factor"]
        * contexto["style_factor"]["msf_visitante"]
        * contexto["motivation"]["cmi_visitante"]
        * contexto["early_impact"]["eii_visitante"]
        * contexto["ajuste_descanso_visitante"]
        * contexto["ajuste_lesiones_visitante"]
    )

    favorito = "L" if local["elo"] >= visita["elo"] else "V"
    if modulo_activo("favorite_fragility") and contexto["fragility"]["ffi"] > 0:
        if favorito == "L":
            lambda_L *= contexto["fragility"]["factor"]
        else:
            lambda_V *= contexto["fragility"]["factor"]

    res = {"L": 0, "E": 0, "V": 0}
    total_goles = 0
    marcadores = Counter()

    for _ in range(sims):
        gl, gv = poisson(lambda_L), poisson(lambda_V)
        total_goles += gl + gv
        marcadores[(gl, gv)] += 1
        if gl > gv:
            res["L"] += 1
        elif gl == gv:
            res["E"] += 1
        else:
            res["V"] += 1

    probs = {k: v / sims for k, v in res.items()}
    draw_boost = contexto["draw_module"]["boost"]
    if draw_boost > 0:
        probs["E"] = min(0.60, probs["E"] + draw_boost)
        squeeze = draw_boost / 2
        probs["L"] = max(0.01, probs["L"] - squeeze)
        probs["V"] = max(0.01, probs["V"] - squeeze)
        total = sum(probs.values())
        probs = {k: v / total for k, v in probs.items()}
        res = {k: int(round(v * sims)) for k, v in probs.items()}

    market_gap = calcular_market_gap(local, visita, probs)

    factores = {
        "liga": contexto["league_key"],
        "bono_jerarquia": bono_jerarquia,
        "influencia_med": influencia_med,
        "boost_fortin": contexto["boost_fortin"],
        "forma_local": contexto["forma_local"]["factor"],
        "forma_visitante": contexto["forma_visitante"]["factor"],
        "carga_local": contexto["carga_local"]["factor_carga"],
        "carga_visitante": contexto["carga_visitante"]["factor_carga"],
        "fatigue_local": contexto["fatigue_local"]["factor"],
        "fatigue_visitante": contexto["fatigue_visitante"]["factor"],
        "opi_local": contexto["opi_local"]["opi"],
        "opi_visitante": contexto["opi_visitante"]["opi"],
        "dls": contexto["draw_module"]["dls"],
        "ffi": contexto["fragility"]["ffi"],
        "msf_local": contexto["style_factor"]["msf_local"],
        "msf_visitante": contexto["style_factor"]["msf_visitante"],
        "mmg": market_gap["mmg"],
        "descanso_local": contexto["ajuste_descanso_local"],
        "descanso_visitante": contexto["ajuste_descanso_visitante"],
        "lesiones_local": contexto["ajuste_lesiones_local"],
        "lesiones_visitante": contexto["ajuste_lesiones_visitante"],
        "memoria_l": bono_mem_l,
        "memoria_v": bono_mem_v,
    }

    return res, marcadores, total_goles, (vl, vv, e), factores, probs, market_gap


def analizar(local, visita, db):
    contexto = construir_contexto_partido(local, visita, db)
    res, marcadores, total_goles, h2h, factores, probs, market_gap = ejecutar_simulacion(local, visita, SIMULACIONES, contexto)

    top_10 = marcadores.most_common(10)
    ganador_porcentaje = max(res, key=res.get)
    marcador_top = marcadores.most_common(1)[0][0]

    if marcador_top[0] > marcador_top[1]:
        ganador_tendencia = "L"
    elif marcador_top[0] == marcador_top[1]:
        ganador_tendencia = "E"
    else:
        ganador_tendencia = "V"

    print(f"\n{'='*60}")
    print(f"🔬 ANÁLISIS TÉCNICO: {local['nombre'].upper()} vs {visita['nombre'].upper()}")

    vl, vv, e = h2h
    if vl > 0 or vv > 0 or e > 0:
        print(f"🧠 MEMORIA DETECTADA (H2H): L({vl}) - E({e}) - V({vv}) -> Ajuste suave.")

    if contexto["invicto_local"] > 5:
        print(
            f"🏰 FORTÍN DETECTADO: {local['nombre']} lleva {contexto['invicto_local']} invicto en casa "
            f"(x{contexto['boost_fortin']:.3f})."
        )

    print(
        f"📊 FORMA REAL (5): {local['nombre']} Pts {contexto['forma_local']['puntos']}, DG {contexto['forma_local']['dg']} | "
        f"{visita['nombre']} Pts {contexto['forma_visitante']['puntos']}, DG {contexto['forma_visitante']['dg']}"
    )
    print(
        f"🏃 CARGA: {local['nombre']} {contexto['carga_local']['partidos_14d']} partidos/14d, "
        f"descanso {contexto['carga_local']['dias_descanso']}d | "
        f"{visita['nombre']} {contexto['carga_visitante']['partidos_14d']} partidos/14d, "
        f"descanso {contexto['carga_visitante']['dias_descanso']}d"
    )

    print(f"{'='*60}")
    print("📈 PROBABILIDADES GENERALES:")
    print(f"   🏠 {local['nombre']}: {(res['L']/SIMULACIONES)*100:.2f}%")
    print(f"   🤝 Empate: {(res['E']/SIMULACIONES)*100:.2f}%")
    print(f"   🚀 {visita['nombre']}: {(res['V']/SIMULACIONES)*100:.2f}%")

    shock = calcular_shock_index(local, visita, res, contexto)
    confianza = clasificar_confianza(probs, contexto)
    if shock >= 0.2:
        print(f"\n⚠️ Potencial sorpresa: {shock*100:.1f}% (valor alto)")
    else:
        print(f"\nℹ️ Potencial sorpresa: {shock*100:.1f}%")

    print("\n🎯 MARCADORES EXACTOS MÁS PROBABLES:")
    for marcador, veces in top_10:
        print(f"   ⚽ {marcador[0]} - {marcador[1]} : {(veces / SIMULACIONES) * 100:.2f}%")

    if ganador_porcentaje != ganador_tendencia:
        nombres_res = {"L": "Local", "E": "Empate", "V": "Visitante"}
        print("\n⚠️  NOTA DEL PREDICTOR: DIVERGENCIA DETECTADA (🌗)")
        print(f"   Favorito por porcentaje: {nombres_res[ganador_porcentaje]}.")
        print(f"   Tendencia por marcador top: {nombres_res[ganador_tendencia]}.")

    print(f"\n⚽ EXPECTATIVA TOTAL DE GOLES: {total_goles / SIMULACIONES:.2f}")
    print("🧾 LOG DE FACTORES (impacto relativo):")
    for k, v in factores.items():
        print(f"   - {k}: x{v:.3f}")
    print(f"{'='*60}\n")


def analizar_partido_jugado(local, visita, gl_real, gv_real, db):
    print(f"\n⏱️ SIMULANDO PARTIDO JUGADO: {local['nombre']} {gl_real} - {gv_real} {visita['nombre']}")
    contexto = construir_contexto_partido(local, visita, db)
    res, marcadores, _, _, _, probs, _ = ejecutar_simulacion(local, visita, SIMULACIONES, contexto)

    ganador_porcentaje = max(res, key=res.get)
    marcador_top = marcadores.most_common(1)[0][0]

    if marcador_top[0] > marcador_top[1]:
        ganador_tendencia = "L"
    elif marcador_top[0] == marcador_top[1]:
        ganador_tendencia = "E"
    else:
        ganador_tendencia = "V"

    if gl_real > gv_real:
        ganador_real = "L"
    elif gl_real == gv_real:
        ganador_real = "E"
    else:
        ganador_real = "V"

    acierto_ganador = ganador_porcentaje == ganador_real
    acierto_resultado_exacto = marcador_top == (gl_real, gv_real)
    acierto_tendencia = (not acierto_ganador) and (ganador_tendencia == ganador_real)

    print("-" * 50)
    if acierto_resultado_exacto:
        print("🚀 ¡ACIERTO DE RESULTADO EXACTO!")
    elif acierto_ganador:
        print("✅ ACIERTO DE GANADOR")
    elif acierto_tendencia:
        print("🌗 ACIERTO EN TENDENCIA (Falló %, acertó marcador top)")
    else:
        print("❌ FALLO TOTAL")

    print(f"➜ Predicción (%): {ganador_porcentaje} | Tendencia: {ganador_tendencia} | Real: {ganador_real}")
    print(f"➜ Marcador Top: {marcador_top[0]}-{marcador_top[1]} | Real: {gl_real}-{gv_real}")
    print("-" * 50)

    confianza = clasificar_confianza(probs, contexto)

    registro = {
        "local": local["nombre"],
        "visitante": visita["nombre"],
        "goles_local": gl_real,
        "goles_visitante": gv_real,
        "acierto_ganador": bool(acierto_ganador),
        "acierto_resultado_exacto": bool(acierto_resultado_exacto),
        "acierto_tendencia": bool(acierto_tendencia),
        "confianza": confianza["nivel"],
    }
    guardar_historial(registro)
    print("💾 Guardado en historial_partidos.json con éxito.\n")


def mostrar_efectividad():
    historial = cargar_historial()
    total = len(historial)
    if total == 0:
        print("\n⚠️ No hay partidos en el historial. Anota algunos con el formato 'EquipoA 1 - 0 EquipoB'.\n")
        return

    aciertos_ganador = sum(1 for p in historial if p["acierto_ganador"])
    exactos = sum(1 for p in historial if p["acierto_resultado_exacto"])
    tendencia = sum(1 for p in historial if p["acierto_tendencia"])

    fallos = total - aciertos_ganador - tendencia

    print(f"\n📊 EFECTIVIDAD ACTUAL DEL PREDICTOR (Muestra de {total} partidos):")
    print(f"✅ = {(aciertos_ganador / total) * 100:.2f}% ({aciertos_ganador}/{total})")
    print(f"🚀 (sobre total) = {(exactos / total) * 100:.2f}% ({exactos}/{total})")
    if aciertos_ganador > 0:
        print(f"🚀 (sobre aciertos) = {(exactos / aciertos_ganador) * 100:.2f}% ({exactos}/{aciertos_ganador})")
    else:
        print("🚀 (sobre aciertos) = 0.00% (0/0)")
    print(f"❌ = {(fallos / total) * 100:.2f}% ({fallos}/{total})")
    print(f"🌗 = {(tendencia / total) * 100:.2f}% ({tendencia}/{total})")
    print("=" * 60 + "\n")


def simular_torneo(equipos_lista, db, ida_vuelta):
    equipos_validos = []
    for eq in equipos_lista:
        k = buscar_equipo(eq, db)
        if k:
            equipos_validos.append(db[k])
        else:
            print(f"❌ Equipo ignorado: {eq}")

    if len(equipos_validos) < 3:
        print("❌ Se necesitan al menos 3 equipos válidos para un torneo.")
        return

    tabla = {eq["nombre"]: {"pts": 0, "pj": 0, "pg": 0, "pe": 0, "pp": 0, "gf": 0, "gc": 0} for eq in equipos_validos}

    if ida_vuelta:
        partidos = list(permutations(equipos_validos, 2))
    else:
        combos = list(combinations(equipos_validos, 2))
        partidos = [(c[0], c[1]) if random.choice([True, False]) else (c[1], c[0]) for c in combos]

    print(f"\n⏳ SIMULANDO TORNEO ({len(partidos)} partidos en total)...")

    for local, visita in partidos:
        contexto = construir_contexto_partido(local, visita, db)
        _, marcadores, _, _, _, _, _ = ejecutar_simulacion(local, visita, 100, contexto)

        resultado_final = marcadores.most_common(1)[0][0]
        gl, gv = resultado_final[0], resultado_final[1]

        nl, nv = local["nombre"], visita["nombre"]
        tabla[nl]["pj"] += 1
        tabla[nv]["pj"] += 1
        tabla[nl]["gf"] += gl
        tabla[nl]["gc"] += gv
        tabla[nv]["gf"] += gv
        tabla[nv]["gc"] += gl

        if gl > gv:
            tabla[nl]["pts"] += 3
            tabla[nl]["pg"] += 1
            tabla[nv]["pp"] += 1
        elif gl == gv:
            tabla[nl]["pts"] += 1
            tabla[nv]["pts"] += 1
            tabla[nl]["pe"] += 1
            tabla[nv]["pe"] += 1
        else:
            tabla[nv]["pts"] += 3
            tabla[nv]["pg"] += 1
            tabla[nl]["pp"] += 1

    orden = sorted(tabla.items(), key=lambda x: (x[1]["pts"], x[1]["gf"] - x[1]["gc"], x[1]["gf"]), reverse=True)

    print(f"\n{'='*80}\n🏆 TABLA DE POSICIONES FINAL\n{'='*80}")
    print(f"{'Pos':<4} | {'Equipo':<25} | {'Pts':<4} | {'PJ':<3} | {'PG':<3} | {'PE':<3} | {'PP':<3} | {'GF':<3} | {'GC':<3} | {'DIF':<4}")
    print("-" * 80)
    for i, (nombre, stats) in enumerate(orden):
        dif = stats["gf"] - stats["gc"]
        print(f"{i+1:<4} | {nombre:<25} | {stats['pts']:<4} | {stats['pj']:<3} | {stats['pg']:<3} | {stats['pe']:<3} | {stats['pp']:<3} | {stats['gf']:<3} | {stats['gc']:<3} | {dif:<4}")
    print(f"{'='*80}\n")


def mostrar_resumen_db(db):
    ligas_dict = {}
    for _, info in db.items():
        l = info["liga"]
        if l not in ligas_dict:
            ligas_dict[l] = []
        ligas_dict[l].append(info["nombre"])

    ligas_lista = sorted(list(ligas_dict.keys()))

    print(f"\n{'='*60}\n📊 ESTADO DE LA BASE DE DATOS\n{'='*60}")
    print(f"✅ Equipos: {len(db)} | 🌍 Ligas: {len(ligas_lista)}\n")
    for i, liga in enumerate(ligas_lista):
        print(f" [{i+1}] {liga}")
    print(f"{'='*60}")

    while True:
        sel = input(">> Ingrese número de liga para ver equipos (o Enter para volver): ").strip()
        if not sel:
            break
        if sel.isdigit() and 1 <= int(sel) <= len(ligas_lista):
            liga_sel = ligas_lista[int(sel)-1]
            equipos_liga = sorted(ligas_dict[liga_sel])
            print(f"\n🏆 EQUIPOS EN {liga_sel.upper()}:")
            for eq in equipos_liga:
                print(f"  • {eq}")
            print("\n")
        else:
            return sel
    return None



def backtesting_rapido(db, max_partidos=100):
    historial = cargar_historial()
    if len(historial) < 5:
        print("\n⚠️ Backtesting no disponible: historial insuficiente.\n")
        return

    muestra = historial[-max_partidos:]
    aciertos = 0
    empates_detectados = 0
    empates_reales = 0

    for p in muestra:
        l_key = normalizar_nombre(p["local"])
        v_key = normalizar_nombre(p["visitante"])
        if l_key not in db or v_key not in db:
            continue

        local, visita = db[l_key], db[v_key]
        contexto = construir_contexto_partido(local, visita, db)
        res, _, _, _, _, _, _ = ejecutar_simulacion(local, visita, 4000, contexto)
        pred = max(res, key=res.get)

        real = "L" if p["goles_local"] > p["goles_visitante"] else "V" if p["goles_local"] < p["goles_visitante"] else "E"
        if real == "E":
            empates_reales += 1
        if pred == "E":
            empates_detectados += 1
        if pred == real:
            aciertos += 1

    total = len(muestra)
    if total == 0:
        print("\n⚠️ Backtesting no ejecutado: sin partidos válidos.\n")
        return

    print("\n📈 BACKTEST RÁPIDO (módulos activos)")
    print(f"   - Partidos evaluados: {total}")
    print(f"   - Precisión 1X2: {(aciertos/total)*100:.2f}%")
    print(f"   - Empates reales: {empates_reales} | Empates predichos: {empates_detectados}")
    print("   - Nota: usar >=100 partidos para comparar módulos on/off con mayor robustez.\n")

def procesar_entrada(entrada, db):
    if entrada == "salir":
        return False

    if entrada == "ef":
        mostrar_efectividad()
        return True

    if entrada == "bt":
        backtesting_rapido(db, max_partidos=100)
        return True

    match_jugado = re.match(r"^(.+?)\s+(\d+)\s*-\s*(\d+)\s+(.+)$", entrada)
    if match_jugado:
        eq_l_str, gl_str, gv_str, eq_v_str = match_jugado.groups()
        l_key = buscar_equipo(eq_l_str, db)
        v_key = buscar_equipo(eq_v_str, db)
        if l_key and v_key:
            analizar_partido_jugado(db[l_key], db[v_key], int(gl_str), int(gv_str), db)
        else:
            print("❌ No se pudieron identificar los equipos para el partido jugado.")
        return True

    if "," in entrada:
        partes = [p.strip() for p in entrada.split(",")]
        if len(partes) >= 2:
            ultimo = partes[-1]
            ida_vuelta, valido = False, False

            if ultimo in ["y", "n"]:
                ida_vuelta = (ultimo == "y")
                partes.pop()
                valido = True
            elif ultimo[-2:] in [" y", " n"]:
                ida_vuelta = (ultimo[-2:] == " y")
                partes[-1] = ultimo[:-2].strip()
                valido = True

            if valido:
                simular_torneo(partes, db, ida_vuelta)
                return True

    if "-" in entrada:
        partes = entrada.split("-")
        if len(partes) == 2:
            l_key = buscar_equipo(partes[0], db)
            v_key = buscar_equipo(partes[1], db)
            if l_key and v_key:
                analizar(db[l_key], db[v_key], db)
            else:
                print("❌ No se pudieron identificar los equipos.")
            return True

    print("⚠️ Formato no reconocido. Usa 'EqA - EqB', 'EqA 1 - 0 EqB', 'ef', 'bt', 'db', o 'Eq1, Eq2, Eq3 Y'")
    return True


def main():
    global LEAGUE_CALIBRATION
    db = cargar_db()
    if not db:
        return
    LEAGUE_CALIBRATION = calibrar_ligas(db)
    print("\n🚀 PREDICTOR v6.0 (Modular avanzado + calibración por liga)")
    while True:
        entrada = input(">> Ingrese comando (o 'salir'): ").lower().strip()

        if entrada == "db":
            comando_pendiente = mostrar_resumen_db(db)
            if comando_pendiente:
                continuar = procesar_entrada(comando_pendiente.lower(), db)
                if not continuar:
                    break
            continue

        continuar = procesar_entrada(entrada, db)
        if not continuar:
            break

if __name__ == "__main__":
    main()
