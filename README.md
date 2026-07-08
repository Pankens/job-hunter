# job-hunter

Panel personal de ofertas de empleo construido con Vue 3 y datos JSON estáticos.

La fuente principal de V1 son feeds/RSS públicos de búsqueda de InfoJobs. No hace
falta `INFOJOBS_CLIENT_ID` ni `INFOJOBS_CLIENT_SECRET`. Si el feed falla o devuelve
0 ofertas, el pipeline usa ofertas mock para mantener la web disponible. No realiza
scraping de páginas de detalle.

## Qué incluye

- Panel principal con ofertas válidas y panel secundario de descartadas.
- Filtros por antigüedad, ciudad, tipo y fuente.
- Estado local de ofertas aplicadas y descartadas manualmente.
- Pipeline Python para obtener RSS, normalizar, deduplicar, filtrar y exportar datos.
- Fallback automático a datos mock.
- Configuración editable de búsquedas y reglas de exclusión.
- Automatizaciones de actualización y despliegue en GitHub Pages.

## Requisitos

- Node.js 20 o superior.
- npm 10 o superior.
- Python 3.10 o superior.

El pipeline usa solo la librería estándar de Python. Para ejecutar tests se instala
únicamente pytest:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## Desarrollo local

La app está dentro de `web/`:

```bash
cd web
npm install
npm run dev
```

Vite mostrará la URL local, normalmente `http://localhost:5173`.

Para generar el JSON que consume la web:

```bash
python scripts/export_jobs.py
```

La salida se escribe en `web/src/data/jobs.json`. Consulta
[`docs/SOURCES.md`](docs/SOURCES.md) para detalles de la fuente InfoJobs RSS.
El fallback está en `data/mock/source_jobs.json`.

## Comandos

| Comando | Acción |
| --- | --- |
| `cd web && npm run dev` | Inicia el frontend en modo desarrollo |
| `cd web && npm run build` | Genera la web de producción en `web/dist/` |
| `cd web && npm run preview` | Previsualiza el build |
| `python scripts/export_jobs.py` | Ejecuta el pipeline InfoJobs RSS → JSON, con fallback mock |

## Pipeline de datos

```text
InfoJobs RSS o data/mock/source_jobs.json
        ↓ normalizar
        ↓ deduplicar
        ↓ aplicar config/filter_rules.json
web/src/data/jobs.json
```

El RSS puede traer fechas RFC 2822 o ISO; el normalizador las convierte a UTC. Los
valores `published_hours_ago` del fallback se convierten en fechas ISO relativas al
momento de exportación.

Los módulos están separados por responsabilidad:

- `scripts/sources/infojobs.py`: consulta y adapta feeds/RSS públicos de InfoJobs.
- `scripts/normalize.py`: transforma fuentes heterogéneas al modelo común.
- `scripts/deduplicate.py`: elimina duplicados por fuente/id y huella de contenido.
- `scripts/filter_jobs.py`: clasifica ofertas y registra motivos de descarte.
- `scripts/export_jobs.py`: coordina el pipeline, muestra logs y escribe el JSON final.

Cada oferta exportada incluye `status`, `reject_reasons`, `match_reasons`,
`warnings` y `matched_skills`. Las rechazadas siguen presentes en el JSON para
alimentar el panel secundario.

`config/filter_rules.json` contiene ubicaciones, términos excluidos, habilidades y
la regla de comisiones. `config/searches.json` define ciudades, consultas RSS y
fuentes activas.

## Estado local

Las acciones **Marcar como aplicada** y **Descartar manualmente** se guardan en
`localStorage` bajo la clave `job-hunter:user-state:v1`. Son privadas del navegador:
no se sincronizan ni se publican en el repositorio.

## GitHub Actions

- `update-jobs.yml`: ejecución manual y cada seis horas. Consulta InfoJobs RSS, usa
  fallback mock si es necesario y solo crea un commit si cambia `jobs.json`.
- `deploy-pages.yml`: compila y publica la web en GitHub Pages al actualizar `main`
  o mediante ejecución manual.

Para desplegar, selecciona **GitHub Actions** como origen en
**Settings → Pages → Build and deployment**. Si el repositorio no se llama
`job-hunter`, el workflow calcula automáticamente la ruta base a partir de su nombre.

## Alcance

InfoJobs está implementado mediante RSS/feed público. La API oficial queda como
opción futura, pero no es requisito de V1. Indeed todavía no está implementado y
LinkedIn queda fuera del alcance, tanto por scraping como por importación manual.
