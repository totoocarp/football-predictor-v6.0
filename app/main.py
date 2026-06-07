from __future__ import annotations

import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import FRONTEND_DIR, load_variable_catalog, load_weights
from app.data_validation import validate_and_complete_match
from app.explanation import build_explanation
from app.gemini_client import GeminiClient, GeminiError
from app.models import PredictionRequest, PredictionResponse
from app.simulation import MonteCarloSimulator
from app.stat_engine import StatisticalEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Predictor de Fútbol Avanzado", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/config")
def public_config() -> dict[str, object]:
    return {"variables": load_variable_catalog(), "weights_metadata": load_weights()["metadata"]}


@app.post("/api/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest) -> PredictionResponse:
    try:
        match, cached = await GeminiClient().get_match_data(request.local, request.visitante, request.force_refresh)
        # Defensive validation keeps stale/manual cache entries or partial Gemini JSON
        # from reaching the rating engine with missing groups.
        match = validate_and_complete_match(match)
        prepared = StatisticalEngine().prepare(match)
        simulation = MonteCarloSimulator().run(match, prepared, request.simulations)
        explanation = build_explanation(match, prepared, simulation)
        return PredictionResponse(
            match=match,
            ratings=prepared.ratings,
            group_influence_percentages=prepared.influence_percentages,
            simulation=simulation,
            explanation=explanation,
            cached=cached,
        )
    except GeminiError as exc:
        logger.exception("Gemini integration failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Prediction failed")
        raise HTTPException(status_code=500, detail=f"No se pudo generar la predicción: {exc}") from exc
