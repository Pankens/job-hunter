"""Diagnóstico de feeds/RSS públicos de InfoJobs.

No genera jobs.json. Solo imprime las URLs consultadas, status HTTP, tamaño,
preview y si se pudo parsear RSS/Atom.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.sources.infojobs import InfoJobsSourceError, fetch_infojobs_jobs

SEARCHES_INPUT = ROOT / "config" / "searches.json"


def main() -> int:
    searches = json.loads(SEARCHES_INPUT.read_text(encoding="utf-8"))
    settings = searches["sources"]["infojobs"]

    print("Prueba local de InfoJobs RSS")
    print("No usa API ni credenciales.")
    try:
        jobs, stats = fetch_infojobs_jobs(settings)
    except InfoJobsSourceError as error:
        stats = error.stats
        print(f"RESULTADO: SIN RSS VÁLIDO ({error})")
        if stats is None:
            return 1
        jobs = []
    else:
        print(f"RESULTADO: RSS VÁLIDO ({len(jobs)} ofertas únicas)")

    print(f"Fuente: {stats.source}")
    print(f"Feeds consultados: {stats.feeds_consulted}")
    print(f"Ofertas obtenidas: {stats.offers_obtained}")
    print()

    for entry in stats.logs:
        print(f"URL: {entry['url']}")
        print(f"  búsqueda: {entry['search']} · ciudad: {entry['city']}")
        print(f"  HTTP: {entry['status']}")
        print(f"  content-type: {entry.get('contentType') or '-'}")
        print(f"  bytes: {entry['responseBytes']}")
        print(f"  RSS válido: {'sí' if entry['validFeed'] else 'no'}")
        print(f"  items parseados: {entry['itemsParsed']}")
        print(f"  motivo: {entry.get('reason') or '-'}")
        print(f"  primeros 300 chars: {entry['preview']}")
        print()

    return 0 if jobs else 2


if __name__ == "__main__":
    raise SystemExit(main())
