# Fuentes de ofertas

## InfoJobs

En V1, InfoJobs es la fuente principal mediante feeds/RSS públicos de búsqueda.
No se usa scraping de páginas de detalle y no hacen falta credenciales.

La integración consulta feeds configurados en `config/searches.json`, normaliza
cada entrada del feed y la pasa por el pipeline común:

```text
InfoJobs RSS → normalize → deduplicate → filter → web/src/data/jobs.json
```

### Búsquedas configuradas

`config/searches.json` genera feeds para:

- Valencia, Paterna y Burjassot.
- Una búsqueda generalista.
- Búsquedas técnicas por término:
  - programador
  - desarrollador
  - frontend
  - backend
  - Java
  - JavaScript
  - TypeScript
  - Vue
  - Angular
  - HTML
  - CSS
  - SCSS
  - Figma
  - MongoDB
  - MySQL
  - diseño web

La plantilla por defecto es:

```text
https://www.infojobs.net/trabajos.feed?keyword={query}&city={city}
```

Si InfoJobs cambia el formato público del feed, basta con ajustar
`feed_url_templates` sin tocar el resto del pipeline.

### Campos disponibles

El RSS intenta extraer:

- `title`
- `company`, si el feed lo expone o si puede inferirse de forma básica desde el título
- `location` / `city`, si está disponible o puede inferirse por la búsqueda
- `published_at`
- `url`
- `summary` / `description`
- `source = infojobs`

El RSS normalmente no entrega la descripción completa de la oferta. Por eso cada
oferta de InfoJobs RSS incorpora el warning:

```text
Descripción limitada por RSS
```

El filtrado seguirá funcionando con el resumen disponible. Si un campo opcional
no aparece en el feed, queda vacío o `null`; el pipeline no falla por ello.

### Logs del exportador

Al ejecutar:

```powershell
python scripts/export_jobs.py
```

se imprimen métricas claras:

- fuente usada
- número de feeds consultados
- número de ofertas obtenidas
- número de ofertas válidas
- número de ofertas descartadas
- si se usó fallback mock y por qué

Además, `web/src/data/jobs.json` guarda `sourceStatus.sourceLogs` con una entrada
por URL consultada:

- URL exacta
- status HTTP
- `Content-Type`
- tamaño de respuesta en bytes
- primeros 300 caracteres recibidos
- si se detectó RSS/Atom válido
- número de items parseados
- motivo del rechazo cuando no es RSS válido

Para depurar la fuente sin regenerar `jobs.json`:

```powershell
python scripts/debug_infojobs_rss.py
```

Este diagnóstico imprime las mismas URLs y metadatos en consola. Si InfoJobs
responde HTML en vez de RSS, quedará visible en el preview.

### Fallback

Si los feeds fallan, devuelven HTML en vez de RSS, XML no válido o no recuperan
ninguna oferta, el exportador usa `data/mock/source_jobs.json`. El JSON final lo indica en
`sourceStatus`:

```json
{
  "mode": "mock-fallback",
  "sourceStatus": {
    "requested": "infojobs",
    "used": "mock",
    "sourceLabel": "Mock",
    "fallback": true,
    "warning": "..."
  }
}
```

Esto mantiene GitHub Pages operativa aunque la fuente pública esté caída o cambie.

### API oficial de InfoJobs

La API oficial queda como opción futura, pero no forma parte del flujo V1. El
código conserva un cliente aislado para esa vía por si más adelante hay acceso al
portal developer y a credenciales de aplicación.

No guardes credenciales en Git. En V1 no hay que configurar
`INFOJOBS_CLIENT_ID` ni `INFOJOBS_CLIENT_SECRET`.

## Indeed

No implementado. Permanece deshabilitado en `config/searches.json`.

## LinkedIn

No se implementa scraping ni importación manual.
