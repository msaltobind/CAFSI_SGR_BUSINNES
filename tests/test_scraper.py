import os
import sys
import types
import unittest
from unittest.mock import patch

import pandas as pd

import scraper


class ModelNotFoundError(Exception):
    code = 404


class FakeModels:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.called_models = []
        self.prompts = []

    def generate_content(self, *, model, contents):
        self.called_models.append(model)
        self.prompts.append(contents)
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return types.SimpleNamespace(text=response)


class AnalizarConGeminiTests(unittest.TestCase):
    def test_404_uses_stable_fallback_default(self):
        models = FakeModels([ModelNotFoundError("model not found"), "<p>Análisis OK</p>"])
        genai = types.ModuleType("google.genai")
        genai.Client = lambda api_key: types.SimpleNamespace(models=models)
        datos = pd.DataFrame(
            [
                {
                    "Moneda": "ARS",
                    "Hon_SD": 0.1,
                    "Patrimonio": 100,
                    "Sociedad_Depositaria": "Banco Industrial",
                }
            ]
        )

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=True), patch.dict(
            sys.modules, {"google.genai": genai}
        ):
            resultado = scraper.analizar_con_gemini(datos)

        self.assertEqual(resultado, "<p>Análisis OK</p>")
        self.assertEqual(
            models.called_models,
            ["gemini-3.8-flash", "gemini-3.5-flash-lite"],
        )

    def test_analysis_prompt_uses_billions_as_trillions_and_separates_currencies(self):
        models = FakeModels(["<p>Análisis OK</p>"])
        genai = types.ModuleType("google.genai")
        genai.Client = lambda api_key: types.SimpleNamespace(models=models)
        datos = pd.DataFrame(
            [
                {
                    "Moneda": "ARS",
                    "Hon_SD": 0.1,
                    "Patrimonio": 1_000_000_000_000,
                    "Sociedad_Depositaria": "Banco de Valores S.A.",
                },
                {
                    "Moneda": "USD",
                    "Hon_SD": 0.2,
                    "Patrimonio": 1_000_000_000_000,
                    "Sociedad_Depositaria": "Banco Comafi S.A.",
                },
            ]
        )

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=True), patch.dict(
            sys.modules, {"google.genai": genai}
        ):
            resultado = scraper.analizar_con_gemini(datos)

        self.assertEqual(resultado, "<p>Análisis OK</p>")
        self.assertIn("AUM 1.00 billones (1 billón = 10^12 ARS)", models.prompts[0])
        self.assertIn("AUM 1.00 billones (1 billón = 10^12 USD)", models.prompts[0])


if __name__ == "__main__":
    unittest.main()
