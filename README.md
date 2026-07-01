# job-hunter

Panel personal de ofertas de empleo construido con Vue 3 y datos JSON estáticos.

La fuente principal es la API oficial de InfoJobs. Si no hay credenciales o la fuente
falla, el pipeline utiliza ofertas mock para mantener la web disponible. **No realiza
scraping.**

## Qué incluye

- Panel principal con ofertas válidas y panel secundario de descartadas.
- Filtros por antigüedad, ciudad, tipo y fuente.
- Estado local de ofertas aplicadas y descartadas manualmente.
- Pipeline Python para normalizar, deduplicar, filtrar y exportar datos.
- Integración con la API oficial de búsqueda de InfoJobs.
- Fallback automático a datos mock.
- Configuración editable de búsquedas y reglas de exclusión.
- Automatizaciones de actualización y despliegue en GitHub Pages.

## Requisitos

- Node.js 20 o superior.
- npm 10 o superior.
- Python 3.10 o superior (sin dependencias externas).

El pipeline no tiene dependencias externas. Para ejecutar los tests se instala
únicamente pytest:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## Desarrollo local

```bash
npm install
npm run dev
```

Vite mostrará la URL local, normalmente `http://localhost:5173`.

Para generar el JSON que consume la web:

```bash
npm run jobs:export
```

También puede ejecutarse directamente:

```bash
python scripts/export_jobs.py
```

La salida se escribe en `web/src/data/jobs.json`. Consulta
[`docs/SOURCES.md`](docs/SOURCES.md) para configurar las credenciales de InfoJobs.
El fallback está en `data/mock/source_jobs.json`.

## Comandos

| Comando | Acción |
| --- | --- |
| `npm run dev` | Inicia el frontend en modo desarrollo |
| `npm run build` | Genera la web de producción en `dist/` |
| `npm run preview` | Previsualiza el build |
| `npm run jobs:export` | Ejecuta el pipeline InfoJobs → JSON, con fallback mock |

## Pipeline de datos

```text
InfoJobs API o data/mock/source_jobs.json
        ↓ normalizar
        ↓ deduplicar
        ↓ aplicar config/filter_rules.json
web/src/data/jobs.json
```

Las fechas RFC 3339 de InfoJobs se conservan en UTC. Los valores
`published_hours_ago` del fallback se convierten en fechas ISO relativas al momento
de exportación.

Los módulos están separados por responsabilidad:

- `scripts/normalize.py`: transforma fuentes heterogéneas al modelo común.
- `scripts/sources/infojobs.py`: consulta y adapta la API oficial de InfoJobs.
- `scripts/deduplicate.py`: elimina duplicados por fuente/id y huella de contenido.
- `scripts/filter_jobs.py`: clasifica ofertas y registra motivos de descarte.
- `scripts/export_jobs.py`: coordina el pipeline y escribe el JSON final.

Cada oferta exportada incluye `status`, `reject_reasons`, `match_reasons`,
`warnings` y `matched_skills`. Las rechazadas siguen presentes en el JSON para
alimentar el panel secundario.

`config/filter_rules.json` contiene ubicaciones, términos excluidos, habilidades y la
regla de comisiones. `config/searches.json` define ciudades, consultas, paginación y
fuentes activas.

## Estado local

Las acciones **Marcar como aplicada** y **Descartar manualmente** se guardan en
`localStorage` bajo la clave `job-hunter:user-state:v1`. Son privadas del navegador:
no se sincronizan ni se publican en el repositorio.

## GitHub Actions

- `update-jobs.yml`: ejecución manual y cada seis horas. Consulta InfoJobs con
  credenciales de GitHub Secrets, usa el fallback si es necesario y solo crea un
  commit si cambia `jobs.json`.
- `deploy-pages.yml`: compila y publica la web en GitHub Pages al actualizar `main` o
  mediante ejecución manual.

Para desplegar, selecciona **GitHub Actions** como origen en
**Settings → Pages → Build and deployment**. Si el repositorio no se llama
`job-hunter`, el workflow calcula automáticamente la ruta base a partir de su nombre.

## Alcance

InfoJobs está implementado mediante su API oficial. Indeed todavía no está
implementado y LinkedIn queda fuera del alcance, tanto por scraping como por
importación manual. Las credenciales viven en variables de entorno o GitHub Secrets,
nunca en el repositorio.
