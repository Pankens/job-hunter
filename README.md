# job-hunter

Panel personal de ofertas de empleo construido con Vue 3 y datos JSON estaticos.

La obtencion de datos usa fuentes publicas reales con APIs JSON: Greenhouse Job
Board API, Lever Postings API y Arbeitnow. Los collectors HTML quedan
desactivados por defecto porque pueden mezclar enlaces de navegacion o categorias
con ofertas reales.

## Que incluye

- Panel principal con ofertas validas y panel secundario de descartadas.
- Filtros por antiguedad, ciudad, tipo y fuente.
- Estado local de ofertas aplicadas y descartadas manualmente.
- Pipeline Python para obtener APIs publicas, normalizar, deduplicar, validar calidad, filtrar y exportar datos.
- Registro configurable de empresas y fuentes en `config/sources.json`.
- Sin fallback mock de publicacion.
- Reportes de ejecucion en `data/last_run_report.json` y `data/source-health.json`.
- Automatizaciones de actualizacion y despliegue en GitHub Pages.

## Requisitos

- Node.js 20 o superior.
- npm 10 o superior.
- Python 3.10 o superior.

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## Desarrollo local

La app esta dentro de `web/`:

```bash
cd web
npm install
npm run dev
```

Para generar el JSON que consume la web:

```bash
python scripts/export_jobs.py
```

La salida se escribe en `web/src/data/jobs.json`.

## Comandos

| Comando | Accion |
| --- | --- |
| `cd web && npm run dev` | Inicia el frontend en modo desarrollo |
| `cd web && npm run build` | Genera la web de produccion en `web/dist/` |
| `python scripts/export_jobs.py` | Ejecuta el pipeline de fuentes reales |

## Pipeline de datos

```text
Greenhouse / Lever / Arbeitnow
        -> normalizar
        -> deduplicar
        -> control de calidad
        -> aplicar config/filter_rules.json
web/src/data/jobs.json
```

Cada oferta valida debe tener titulo real, empresa, URL directa a una oferta
individual, ubicacion o modalidad remota y descripcion suficiente para aplicar
filtros. `publishedAt` queda en `null` si la fuente no proporciona fecha de
publicacion; `firstSeenAt` indica cuando el pipeline vio la oferta.

Las rechazadas siguen presentes en el JSON para alimentar el panel secundario,
con `reject_reasons`, `match_reasons`, `warnings` y `matched_skills`.

## Fuentes

`config/sources.json` contiene el registro activo:

- `greenhouse`: tableros corporativos Greenhouse, por ejemplo GitLab, Mozilla, Okta y Cloudflare.
- `lever`: tableros corporativos Lever, actualmente Wealthfront.
- `arbeitnow`: API publica sin clave para empleo tecnico/remoto.
- `*_html`: conservados para depuracion, pero apagados por defecto.

Si una fuente falla, el error queda en `data/source-health.json` y las demas
fuentes siguen publicando resultados. Si todas fallan, se publica un estado vacio
real; nunca se publican mocks.

## Perfiles y exclusiones

Se mantienen dos perfiles:

- general: tienda, atencion al cliente, administracion, almacen, limpieza y hosteleria.
- tecnico: desarrollo, IT y diseno.

Tambien se conservan las exclusiones de autonomo, venta fria/calle, carnet o
vehiculo obligatorio, discapacidad obligatoria, practicas, idiomas obligatorios
distintos de espanol/ingles y solo comisiones sin fijo suficiente.

## Estado local

Las acciones **Marcar como aplicada** y **Descartar manualmente** se guardan en
`localStorage` bajo la clave `job-hunter:user-state:v1`. Son privadas del navegador.

## GitHub Actions

- `update-jobs.yml`: ejecucion manual y cada seis horas. Consulta fuentes reales,
  escribe `jobs.json`, `last_run_report.json` y `source-health.json`, y solo crea
  commit si cambian.
- `deploy-pages.yml`: compila y publica la web en GitHub Pages al actualizar `main`
  o mediante ejecucion manual.
