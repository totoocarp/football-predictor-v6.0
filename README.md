# Predictor de Fútbol Avanzado con Simulación Monte Carlo

Aplicación web modular construida con FastAPI, NumPy, Pandas y SciPy. El frontend está hecho con HTML, CSS y JavaScript; el motor estadístico y la simulación se ejecutan exclusivamente en Python.

## Ejecución

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export GEMINI_API_KEY="tu_api_key"
uvicorn app.main:app --reload
```

Abre `http://localhost:8000`.

## Arquitectura

- `app/gemini_client.py`: integración con Gemini 2.5 Flash y prompt estricto de fuentes; Gemini solo devuelve datos, no ratings ni predicciones.
- `app/gemini_client.py`: integración con Gemini 2.5 Flash y prompt estricto de fuentes.
- `app/cache.py`: caché local de consultas durante 24 horas.
- `app/models.py`: validación Pydantic.
- `app/stat_catalog.py` y `config/stat_variables.json`: catálogo de 118 variables obligatorias.
- `config/weights.json`: pesos de grupos y variables prioritarias.
- `app/stat_engine.py`: normalización, ponderación y ratings.
- `app/simulation.py`: simulación Monte Carlo vectorizada con NumPy/Pandas y Poisson de SciPy.
- `app/explanation.py`: explicación y factores clave.
- `frontend/`: visualización de resultados.

## Diseño para futuro ML

El motor consume variables y pesos desde configuración. Para reemplazar los pesos manuales por Random Forest, XGBoost, LightGBM o redes neuronales, se puede generar un archivo de importancias con las mismas claves `grupo.variable` y reutilizar el pipeline de normalización y simulación.
