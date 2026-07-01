# job-hunter

Panel personal de ofertas de empleo construido con Vue 3 y datos JSON estáticos.

Esta primera iteración es deliberadamente local y reproducible: usa ofertas mock para
probar la interfaz y el pipeline de datos. **Todavía no realiza scraping ni peticiones a
InfoJobs, Indeed, LinkedIn u otras fuentes.**

## Qué incluye

- Panel principal con ofertas válidas y panel secundario de descartadas.
- Filtros por antigüedad, ciudad, tipo y fuente.
- Estado local de ofertas aplicadas y descartadas manualmente.
- Pipeline Python para normalizar, deduplicar, filtrar y exportar datos.
- Configuración editable de búsquedas y reglas de exclusión.
- Automatizaciones de actualización y despliegue en GitHub Pages.

## Requisitos

- Node.js 20 o superior.
- npm 10 o superior.
- Python 3.10 o superior (sin dependencias externas).

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

La salida se escribe en `web/src/data/jobs.json`. El archivo de entrada mock está en
`data/mock/source_jobs.json`.

## Comandos

| Comando | Acción |
| --- | --- |
| `npm run dev` | Inicia el frontend en modo desarrollo |
| `npm run build` | Genera la web de producción en `dist/` |
| `npm run preview` | Previsualiza el build |
| `npm run jobs:export` | Ejecuta el pipeline mock en Python |

## Pipeline de datos

```text
data/mock/source_jobs.json
        ↓ normalizar
        ↓ deduplicar
        ↓ aplicar config/filter_rules.json
web/src/data/jobs.json
```

Los valores `published_hours_ago` de los mocks se convierten en fechas ISO relativas
al momento de exportación. Esto permite probar siempre los filtros de 24 h a 7 días.

Los módulos están separados por responsabilidad:

- `scripts/normalize.py`: transforma fuentes heterogéneas al modelo común.
- `scripts/deduplicate.py`: elimina duplicados por fuente/id y huella de contenido.
- `scripts/filter_jobs.py`: clasifica ofertas y registra motivos de descarte.
- `scripts/export_jobs.py`: coordina el pipeline y escribe el JSON final.

`config/filter_rules.json` contiene ubicaciones, términos excluidos, habilidades y la
regla de comisiones. `config/searches.json` reserva la configuración de futuras
integraciones, actualmente deshabilitadas.

## Estado local

Las acciones **Marcar como aplicada** y **Descartar manualmente** se guardan en
`localStorage` bajo la clave `job-hunter:user-state:v1`. Son privadas del navegador:
no se sincronizan ni se publican en el repositorio.

## GitHub Actions

- `update-jobs.yml`: ejecución manual y cada seis horas. En V1 regenera los mocks y
  solo crea un commit si cambia `jobs.json`.
- `deploy-pages.yml`: compila y publica la web en GitHub Pages al actualizar `main` o
  mediante ejecución manual.

Para desplegar, selecciona **GitHub Actions** como origen en
**Settings → Pages → Build and deployment**. Si el repositorio no se llama
`job-hunter`, el workflow calcula automáticamente la ruta base a partir de su nombre.

## Alcance y próximos pasos

No se ha implementado scraping real. La siguiente iteración puede incorporar primero
InfoJobs mediante API oficial o endpoints expresamente permitidos y tratar Indeed como
fuente experimental. LinkedIn queda fuera de V1, tanto por scraping como por
importación manual.

Antes de activar una fuente real conviene revisar sus términos, límites de uso,
autenticación y política de almacenamiento. Las credenciales deberán vivir en GitHub
Secrets, nunca en el repositorio.
