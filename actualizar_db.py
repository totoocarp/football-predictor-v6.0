import soccerdata as sd
import json
import requests
import pandas as pd
import io

def generar_base_datos():
    print("⏳ INICIANDO ACTUALIZACIÓN MUNDIAL (CLUBES + SELECCIONES)...")
    db_final = {}

    try:
        print("\n🌍 [1/3] Descargando Clubes de Europa (ClubElo)...")
        elo_client = sd.ClubElo()
        elo_stats = elo_client.read_by_date()
        for equipo, row in elo_stats.iterrows():
            puntos = row['elo']
            if puntos < 1350: continue
            nombre_key = equipo.lower().strip()
            base = (puntos - 1000) / 10.8
            db_final[nombre_key] = {
                "nombre": equipo, "ataque": int(base + 2), "mediocampo": int(base),
                "defensa": int(base - 2), "forma": 1.0, "elo": puntos,
                "liga": row['country'] + " (Europa)"
            }
        print("   ✅ Clubes Europeos añadidos.")
    except Exception as e:
        print(f"   ❌ Error en Europa: {e}")

    print("\n🏳️ [2/3] Añadiendo Selecciones Nacionales...")
    fifa_top = [
        ("España", 1990), ("Argentina", 1985), ("Francia", 1980), ("Inglaterra", 1940),
        ("Brasil", 1880), ("Colombia", 1815), ("Uruguay", 1775), ("Alemania", 1835),
        ("Portugal", 1770), ("Paises Bajos", 1765), ("Italia", 1710), ("Croacia", 1720)
    ]
    for pais, puntos in fifa_top:
        nombre_key = pais.lower().strip()
        base = (puntos - 1000) / 10.8
        db_final[nombre_key] = {
            "nombre": f"{pais} (Sel)", "ataque": int(base + 3), "mediocampo": int(base + 1),
            "defensa": int(base), "forma": 1.0, "elo": puntos, "liga": "Internacional"
        }
    print("   ✅ Selecciones añadidas.")

    print("\n🌎 [3/3] Scrapeando Ligas de América (ELO Real)...")
    urls = [
        ("https://footballdatabase.com/ranking/south-america", "CONMEBOL"),
        ("https://footballdatabase.com/ranking/north-america", "CONCACAF")
    ]
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    }
    
    paises_america = [
        "Brazil", "Argentina", "Colombia", "Uruguay", "Chile", "Ecuador", "Peru", 
        "Paraguay", "Bolivia", "Venezuela", "Mexico", "USA", "Costa Rica", 
        "Honduras", "Panama", "Guatemala", "El Salvador", "Canada", "Jamaica"
    ]

    for url, confed in urls:
        count_ame = 0
        try:
            r = requests.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            tablas = pd.read_html(io.StringIO(r.text))
            df = tablas[0]
            for _, row in df.iterrows():
                try:
                    # Obtenemos el texto crudo (ej: "1121529")
                    raw_puntos = str(row.iloc[3]).strip()
                    
                    # Extraemos solo los últimos 4 dígitos (los puntos Elo reales)
                    if len(raw_puntos) >= 4:
                        puntos = int(raw_puntos[-4:])
                    else:
                        puntos = int(raw_puntos) # Por si acaso el formato viene limpio
                except ValueError:
                    continue

                equipo = str(row.iloc[1]).strip()
                if puntos < 1300: continue
                
                for pais in paises_america:
                    if equipo.endswith(pais):
                        equipo = equipo[:-len(pais)].strip()
                        break
                
                nombre_key = equipo.lower().strip()
                if nombre_key in db_final: continue
                
                base = (puntos - 1000) / 10.8
                db_final[nombre_key] = {
                    "nombre": equipo, "ataque": int(base), "mediocampo": int(base),
                    "defensa": int(base), "forma": 1.0, "elo": puntos,
                    "liga": f"{confed} (América)"
                }
                count_ame += 1
            print(f"   ✅ {count_ame} clubes de {confed} añadidos.")
        except Exception as e:
            print(f"   ❌ Error scrapeando {confed}: {e}")

    with open("equipos.json", "w", encoding="utf-8") as f:
        json.dump(db_final, f, indent=4, ensure_ascii=False)
    print(f"\n✨ BASE DE DATOS FINALIZADA: {len(db_final)} Equipos.")

if __name__ == "__main__":
    generar_base_datos()