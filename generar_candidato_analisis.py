import json
from pathlib import Path

import pandas as pd

from scraper import analizar_con_gemini


def generar_candidato(origen: Path, destino: Path) -> None:
    if origen.resolve() == destino.resolve():
        raise ValueError("El archivo candidato no puede reemplazar el JSON de origen")

    datos = json.loads(origen.read_text(encoding="utf-8"))
    fondos = datos.get("fondos")
    if not isinstance(fondos, list) or not fondos:
        raise ValueError("El JSON de origen no contiene fondos para analizar")

    resumen = analizar_con_gemini(pd.DataFrame(fondos))
    if "fuera de servicio" in resumen or "API Key no configurada" in resumen:
        raise RuntimeError("Gemini no generó el análisis; el JSON original no fue modificado")

    candidato = {**datos, "resumen_ia": resumen}
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(candidato, ensure_ascii=False, indent=4),
        encoding="utf-8",
    )
    print(f"Candidato generado: {destino}")


if __name__ == "__main__":
    generar_candidato(
        Path("docs/data.json"),
        Path("candidate/docs/data.json"),
    )