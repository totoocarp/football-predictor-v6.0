from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.cache import read_cached_match, write_cached_match
from app.config import ALLOWED_SOURCES, GEMINI_API_KEY, GEMINI_ENDPOINT, GEMINI_MODEL, load_variable_catalog
from app.data_validation import validate_and_complete_match
from app.models import MatchData

logger = logging.getLogger(__name__)


class GeminiError(RuntimeError):
    pass


class GeminiClient:
    def __init__(self, api_key: str = GEMINI_API_KEY, model: str = GEMINI_MODEL) -> None:
        self.api_key = api_key
        self.model = model

    async def get_match_data(self, home: str, away: str, force_refresh: bool = False) -> tuple[MatchData, bool]:
        if not force_refresh:
            cached = read_cached_match(home, away)
            if cached is not None:
                logger.info("Cache hit for %s vs %s", home, away)
                return validate_and_complete_match(MatchData.model_validate(cached)), True

        if not self.api_key:
            raise GeminiError("Falta GEMINI_API_KEY. Configura la variable de entorno para consultar Gemini 2.5 Flash.")

        prompt = self._build_prompt(home, away)
        raw_text = await self._request(prompt)
        parsed = self._parse_json(raw_text)
        match_data = validate_and_complete_match(MatchData.model_validate(parsed))
        write_cached_match(home, away, match_data.model_dump(mode="json"))
        return match_data, False

    def _build_prompt(self, home: str, away: str) -> str:
        catalog = load_variable_catalog()
        return f"""
Eres un recolector estricto de datos futbolísticos para un motor estadístico en Python.
Partido: local={home}; visitante={away}.

REGLAS ABSOLUTAS:
- Usa únicamente estas fuentes: {', '.join(ALLOWED_SOURCES)}.
- No inventes estadísticas. No estimes. No infieras.
- Si un dato no existe o no puede verificarse: valor=null y confianza=LOW.
- Cada estadística debe tener exactamente: {{"valor": número|string|null, "fuente": "Nombre fuente", "confianza": "HIGH|MEDIUM|LOW"}}.
- Devuelve solo JSON válido, sin Markdown, sin comentarios, sin texto fuera del JSON.
- Si una variable está condicionada al partido, interpreta el equipo local como local y el visitante como visitante.

CATÁLOGO OBLIGATORIO DE VARIABLES:
{json.dumps(catalog, ensure_ascii=False)}

FORMATO EXACTO DE RESPUESTA:
{{
  "local": {{"nombre": "{home}", "estadisticas": {{...}}, "fortalezas": [], "debilidades": [], "notas_fuentes": []}},
  "visitante": {{"nombre": "{away}", "estadisticas": {{...}}, "fortalezas": [], "debilidades": [], "notas_fuentes": []}},
  "contexto": {{"fecha_consulta": "ISO-8601", "fuentes_permitidas": {json.dumps(ALLOWED_SOURCES)}}}
}}
""".strip()

    async def _request(self, prompt: str) -> str:
        url = GEMINI_ENDPOINT.format(model=self.model)
        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.0, "responseMimeType": "application/json"},
        }
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(f"{url}?key={self.api_key}", json=payload)
        if response.status_code >= 400:
            logger.error("Gemini error %s: %s", response.status_code, response.text[:1000])
            raise GeminiError(f"Gemini devolvió HTTP {response.status_code}.")
        data = response.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise GeminiError("Gemini no devolvió texto utilizable.") from exc

    @staticmethod
    def _parse_json(raw_text: str) -> dict[str, Any]:
        text = raw_text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text).strip()
            text = re.sub(r"```$", "", text).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            match = re.search(r"\{.*\}", text, flags=re.S)
            if match:
                return json.loads(match.group(0))
            raise GeminiError("La respuesta de Gemini no contiene JSON válido.") from exc
