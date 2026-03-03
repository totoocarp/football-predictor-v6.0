import json
import math
import random
import os
import re
import urllib.request
import urllib.error
from bs4 import BeautifulSoup
from difflib import get_close_matches
from collections import Counter
from itertools import permutations, combinations

SIMULACIONES = 50000
FACTOR_LOCALIA = 1.12
ARCHIVO_HISTORIAL = "historial_partidos.json"

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

def buscar_equipo(nombre_usuario, db):
    nombre_limpio = nombre_usuario.lower().strip()
    if nombre_limpio in ALIAS: nombre_limpio = ALIAS[nombre_limpio]
    if nombre_limpio in db: return nombre_limpio
    coincidencias = get_close_matches(nombre_limpio, db.keys(), n=3, cutoff=0.6)
    if coincidencias:
        print(f"\n🤔 No encontré '{nombre_usuario}'. ¿Tal vez?")
        for i, pos in enumerate(coincidencias): print(f"  {i+1}. {db[pos]['nombre']}")
        rta = input("Selecciona número o Enter para cancelar: ")
        if rta.isdigit() and 1 <= int(rta) <= len(coincidencias): return coincidencias[int(rta)-1]
    return None

def obtener_invicto_local_real(equipo):
    nombre_keyword = "city" 
    slug = "manchester-city-fc"
    url = f"https://es.besoccer.com/equipo/partidos/{slug}"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9',
            'Referer': 'https://www.google.com/'
        }
        
        req = urllib.request.Request(url, headers=headers)
        response = urllib.request.urlopen(req, timeout=15)
        html = response.read().decode('utf-8')
        soup = BeautifulSoup(html, 'html.parser')

        eventos = soup.find_all(['tr', 'div'], class_=re.compile(r'match|panel-body'))
        
        invicto_local = 0
        partidos_procesados = 0
        
        for evento in reversed(eventos):
            marcador_link = evento.find('a', href=re.compile(r'/partido/'))
            if not marcador_link: continue
                
            texto_marcador = marcador_link.get_text(strip=True)
            if '-' not in texto_marcador: continue

            nombres_equipos = evento.select('.team-name')
            if len(nombres_equipos) < 2: continue
                
            local = nombres_equipos[0].get_text(strip=True).lower()
            visitante = nombres_equipos[1].get_text(strip=True).lower()

            if nombre_keyword not in local: continue

            clase_marcador = str(marcador_link.get('class', '')) + str(evento.get('class', ''))
            
            if 'res-l' in clase_marcador:
                break
            elif 'res-w' in clase_marcador or 'res-d' in clase_marcador:
                invicto_local += 1
                partidos_procesados += 1
            else:
                continue

        return min(invicto_local, 15)

    except Exception as e:
        return 0

def calcular_memoria_historica(nombre_l, nombre_v):
    historial = cargar_historial()
    vl, vv, empates = 0, 0, 0
    
    for p in historial:
        if p['local'] == nombre_l and p['visitante'] == nombre_v:
            if p['goles_local'] > p['goles_visitante']: vl += 1
            elif p['goles_local'] < p['goles_visitante']: vv += 1
            else: empates += 1
        elif p['local'] == nombre_v and p['visitante'] == nombre_l:
            if p['goles_local'] < p['goles_visitante']: vl += 1
            elif p['goles_local'] > p['goles_visitante']: vv += 1
            else: empates += 1
            
    # Ajuste leve: +2% por victoria previa, +1% por empate
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

def ejecutar_simulacion(local, visita, sims, fortin_real):
    dif_elo = local['elo'] - visita['elo']
    bono_jerarquia = 1 + (dif_elo / 1200)
    dif_med = local['mediocampo'] - visita['mediocampo']
    influencia_med = 1 + (dif_med * 0.008)

    bono_fortin = 1.0
    if fortin_real >= 5:
        bono_fortin = 1 + (math.log10(fortin_real) * 0.1)

    # Aplicamos Memoria Histórica
    bono_mem_l, bono_mem_v, vl, vv, e = calcular_memoria_historica(local['nombre'], visita['nombre'])

    lambda_L = ((local['ataque'] * 0.6 + local['mediocampo'] * 0.4) / (visita['defensa'] * 0.8 + 20)) \
        * FACTOR_LOCALIA * local['forma'] * bono_jerarquia * influencia_med * bono_fortin * bono_mem_l

    lambda_V = ((visita['ataque'] * 0.6 + visita['mediocampo'] * 0.4) / (local['defensa'] * 0.8 + 20)) \
        * visita['forma'] / (bono_jerarquia if bono_jerarquia != 0 else 1) / influencia_med * bono_mem_v

    res = {"L": 0, "E": 0, "V": 0}
    total_goles = 0
    marcadores = Counter()

    for _ in range(sims):
        gl, gv = poisson(lambda_L), poisson(lambda_V)
        total_goles += (gl + gv)
        marcadores[(gl, gv)] += 1
        if gl > gv: res["L"] += 1
        elif gl == gv: res["E"] += 1
        else: res["V"] += 1
        
    return res, marcadores, total_goles, (vl, vv, e)

def analizar(local, visita):
    invicto = obtener_invicto_local_real(local)
    res, marcadores, total_goles, h2h = ejecutar_simulacion(local, visita, SIMULACIONES, invicto)

    top_10 = marcadores.most_common(10)
    ganador_porcentaje = max(res, key=res.get) 
    marcador_top = marcadores.most_common(1)[0][0]
    
    if marcador_top[0] > marcador_top[1]: ganador_tendencia = "L"
    elif marcador_top[0] == marcador_top[1]: ganador_tendencia = "E"
    else: ganador_tendencia = "V"

    print(f"\n{'='*60}")
    print(f"🔬 ANÁLISIS TÉCNICO: {local['nombre'].upper()} vs {visita['nombre'].upper()}")
    
    vl, vv, e = h2h
    if vl > 0 or vv > 0 or e > 0:
        print(f"🧠 MEMORIA DETECTADA (H2H): L({vl}) - E({e}) - V({vv}) -> Aplicando ajuste suave.")
    
    if invicto >= 5:
        print(f"🏰 FORTÍN DETECTADO: {local['nombre']} lleva {invicto} partidos invicto en casa (Bono aplicado).")
    print(f"{'='*60}")
    
    print(f"📈 PROBABILIDADES GENERALES:")
    print(f"   🏠 {local['nombre']}: {(res['L']/SIMULACIONES)*100:.2f}%")
    print(f"   🤝 Empate: {(res['E']/SIMULACIONES)*100:.2f}%")
    print(f"   🚀 {visita['nombre']}: {(res['V']/SIMULACIONES)*100:.2f}%")
    
    print(f"\n🎯 MARCADORES EXACTOS MÁS PROBABLES:")
    for marcador, veces in top_10:
        print(f"   ⚽ {marcador[0]} - {marcador[1]} : {(veces / SIMULACIONES) * 100:.2f}%")

    if ganador_porcentaje != ganador_tendencia:
        nombres_res = {"L": "Local", "E": "Empate", "V": "Visitante"}
        print(f"\n⚠️  NOTA DEL PREDICTOR: DIVERGENCIA DETECTADA (🌗)")
        print(f"   Los porcentajes dan como favorito al {nombres_res[ganador_porcentaje].upper()}, pero")
        print(f"   el marcador exacto más repetido indica tendencia al {nombres_res[ganador_tendencia].upper()}.")

    print(f"\n⚽ EXPECTATIVA TOTAL DE GOLES: {total_goles / SIMULACIONES:.2f}")
    print(f"{'='*60}\n")

def analizar_partido_jugado(local, visita, gl_real, gv_real):
    print(f"\n⏱️ SIMULANDO PARTIDO JUGADO: {local['nombre']} {gl_real} - {gv_real} {visita['nombre']}")
    invicto = obtener_invicto_local_real(local)
    res, marcadores, _, _ = ejecutar_simulacion(local, visita, SIMULACIONES, invicto)
    
    ganador_porcentaje = max(res, key=res.get) 
    marcador_top = marcadores.most_common(1)[0][0]
    
    if marcador_top[0] > marcador_top[1]: ganador_tendencia = "L"
    elif marcador_top[0] == marcador_top[1]: ganador_tendencia = "E"
    else: ganador_tendencia = "V"
    
    if gl_real > gv_real: ganador_real = "L"
    elif gl_real == gv_real: ganador_real = "E"
    else: ganador_real = "V"
    
    acierto_ganador = (ganador_porcentaje == ganador_real)
    acierto_resultado_exacto = (marcador_top == (gl_real, gv_real))
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
    
    registro = {
        "local": local['nombre'],
        "visitante": visita['nombre'],
        "goles_local": gl_real,
        "goles_visitante": gv_real,
        "acierto_ganador": bool(acierto_ganador),
        "acierto_resultado_exacto": bool(acierto_resultado_exacto),
        "acierto_tendencia": bool(acierto_tendencia)
    }
    guardar_historial(registro)
    print("💾 Guardado en historial_partidos.json con éxito.\n")

def mostrar_efectividad():
    historial = cargar_historial()
    total = len(historial)
    if total == 0:
        print("\n⚠️ No hay partidos en el historial. Anota algunos con el formato 'EquipoA 1 - 0 EquipoB'.\n")
        return
        
    aciertos_ganador = sum(1 for p in historial if p['acierto_ganador'])
    exactos = sum(1 for p in historial if p['acierto_resultado_exacto'])
    tendencia = sum(1 for p in historial if p['acierto_tendencia'])
    
    fallos = total - aciertos_ganador - tendencia
    
    print(f"\n📊 EFECTIVIDAD ACTUAL DEL PREDICTOR (Muestra de {total} partidos):")
    print(f"✅ = {(aciertos_ganador / total) * 100:.2f}% ({aciertos_ganador}/{total})")
    print(f"🚀 (sobre total) = {(exactos / total) * 100:.2f}% ({exactos}/{total})")
    if aciertos_ganador > 0:
        print(f"🚀 (sobre aciertos) = {(exactos / aciertos_ganador) * 100:.2f}% ({exactos}/{aciertos_ganador})")
    else:
        print(f"🚀 (sobre aciertos) = 0.00% (0/0)")
    print(f"❌ = {(fallos / total) * 100:.2f}% ({fallos}/{total})")
    print(f"🌗 = {(tendencia / total) * 100:.2f}% ({tendencia}/{total})")
    print("="*60 + "\n")

def simular_torneo(equipos_lista, db, ida_vuelta):
    equipos_validos = []
    for eq in equipos_lista:
        k = buscar_equipo(eq, db)
        if k: equipos_validos.append(db[k])
        else: print(f"❌ Equipo ignorado: {eq}")
        
    if len(equipos_validos) < 3:
        print("❌ Se necesitan al menos 3 equipos válidos para un torneo.")
        return

    tabla = {eq['nombre']: {'pts': 0, 'pj': 0, 'pg': 0, 'pe': 0, 'pp': 0, 'gf': 0, 'gc': 0} for eq in equipos_validos}
    
    if ida_vuelta: partidos = list(permutations(equipos_validos, 2))
    else:
        combos = list(combinations(equipos_validos, 2))
        partidos = [(c[0], c[1]) if random.choice([True, False]) else (c[1], c[0]) for c in combos]

    print(f"\n⏳ SIMULANDO TORNEO ({len(partidos)} partidos en total)...")
    
    for local, visita in partidos:
        _, marcadores, _, _ = ejecutar_simulacion(local, visita, 100, obtener_invicto_local_real(local))
        
        resultado_final = marcadores.most_common(1)[0][0]
        gl, gv = resultado_final[0], resultado_final[1]
        
        nl, nv = local['nombre'], visita['nombre']
        tabla[nl]['pj'] += 1
        tabla[nv]['pj'] += 1
        tabla[nl]['gf'] += gl
        tabla[nl]['gc'] += gv
        tabla[nv]['gf'] += gv
        tabla[nv]['gc'] += gl
        
        if gl > gv:
            tabla[nl]['pts'] += 3
            tabla[nl]['pg'] += 1
            tabla[nv]['pp'] += 1
        elif gl == gv:
            tabla[nl]['pts'] += 1
            tabla[nv]['pts'] += 1
            tabla[nl]['pe'] += 1
            tabla[nv]['pe'] += 1
        else:
            tabla[nv]['pts'] += 3
            tabla[nv]['pg'] += 1
            tabla[nl]['pp'] += 1

    orden = sorted(tabla.items(), key=lambda x: (x[1]['pts'], x[1]['gf'] - x[1]['gc'], x[1]['gf']), reverse=True)

    print(f"\n{'='*80}\n🏆 TABLA DE POSICIONES FINAL\n{'='*80}")
    print(f"{'Pos':<4} | {'Equipo':<25} | {'Pts':<4} | {'PJ':<3} | {'PG':<3} | {'PE':<3} | {'PP':<3} | {'GF':<3} | {'GC':<3} | {'DIF':<4}")
    print("-" * 80)
    for i, (nombre, stats) in enumerate(orden):
        dif = stats['gf'] - stats['gc']
        print(f"{i+1:<4} | {nombre:<25} | {stats['pts']:<4} | {stats['pj']:<3} | {stats['pg']:<3} | {stats['pe']:<3} | {stats['pp']:<3} | {stats['gf']:<3} | {stats['gc']:<3} | {dif:<4}")
    print(f"{'='*80}\n")

def mostrar_resumen_db(db):
    ligas_dict = {}
    for key, info in db.items():
        l = info['liga']
        if l not in ligas_dict: ligas_dict[l] = []
        ligas_dict[l].append(info['nombre'])
    
    ligas_lista = sorted(list(ligas_dict.keys()))
    
    print(f"\n{'='*60}\n📊 ESTADO DE LA BASE DE DATOS\n{'='*60}")
    print(f"✅ Equipos: {len(db)} | 🌍 Ligas: {len(ligas_lista)}\n")
    for i, liga in enumerate(ligas_lista): print(f" [{i+1}] {liga}")
    print(f"{'='*60}")
    
    while True:
        sel = input(">> Ingrese número de liga para ver equipos (o Enter para volver): ").strip()
        if not sel: break
        if sel.isdigit() and 1 <= int(sel) <= len(ligas_lista):
            liga_sel = ligas_lista[int(sel)-1]
            equipos_liga = sorted(ligas_dict[liga_sel])
            print(f"\n🏆 EQUIPOS EN {liga_sel.upper()}:")
            for eq in equipos_liga: print(f"  • {eq}")
            print("\n")
        else:
            return sel 
    return None

def procesar_entrada(entrada, db):
    if entrada == 'salir': return False
    
    if entrada == 'ef':
        mostrar_efectividad()
        return True

    match_jugado = re.match(r'^(.+?)\s+(\d+)\s*-\s*(\d+)\s+(.+)$', entrada)
    if match_jugado:
        eq_l_str, gl_str, gv_str, eq_v_str = match_jugado.groups()
        l_key = buscar_equipo(eq_l_str, db)
        v_key = buscar_equipo(eq_v_str, db)
        if l_key and v_key:
            analizar_partido_jugado(db[l_key], db[v_key], int(gl_str), int(gv_str))
        else:
            print("❌ No se pudieron identificar los equipos para el partido jugado.")
        return True

    if "," in entrada:
        partes = [p.strip() for p in entrada.split(",")]
        if len(partes) >= 2:
            ultimo = partes[-1]
            ida_vuelta, valido = False, False
            
            if ultimo in ['y', 'n']:
                ida_vuelta = (ultimo == 'y')
                partes.pop()
                valido = True
            elif ultimo[-2:] in [' y', ' n']:
                ida_vuelta = (ultimo[-2:] == ' y')
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
                analizar(db[l_key], db[v_key])
            else:
                print("❌ No se pudieron identificar los equipos.")
            return True
            
    print("⚠️ Formato no reconocido. Usa 'EqA - EqB', 'EqA 1 - 0 EqB', 'ef', 'db', o 'Eq1, Eq2, Eq3 Y'")
    return True

def main():
    db = cargar_db()
    if not db: return
    print("\n🚀 PREDICTOR v6.0 (Con Memoria Histórica y Efectividad)")
    while True:
        entrada = input(">> Ingrese comando (o 'salir'): ").lower().strip()
        
        if entrada == 'db':
            comando_pendiente = mostrar_resumen_db(db)
            if comando_pendiente:
                continuar = procesar_entrada(comando_pendiente.lower(), db)
                if not continuar: break
            continue
            
        continuar = procesar_entrada(entrada, db)
        if not continuar: break

if __name__ == "__main__":
    main()