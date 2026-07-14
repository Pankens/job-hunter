# Fuentes de ofertas

El pipeline publica solo fuentes reales. No hay fallback mock y los collectors
HTML estan apagados por defecto.

## Registro

La configuracion vive en `config/sources.json`.

- `sources`: activa o desactiva cada adaptador.
- `source_registry.greenhouse.companies`: tableros Greenhouse por `board`.
- `source_registry.lever.companies`: tableros Lever por `company`.
- `source_registry.arbeitnow`: API publica sin clave.
- `html_collectors.enabled`: debe seguir en `false` salvo depuracion manual.

## Greenhouse Job Board API

Endpoint por empresa:

```text
https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true
```

Campos usados:

- `id`
- `title`
- `absolute_url`
- `content`
- `location.name`
- `offices`

Greenhouse no siempre proporciona fecha de publicacion. Cuando no existe,
`publishedAt` queda en `null` y el exportador usa `firstSeenAt` solo como fecha
de deteccion.

## Lever Postings API

Endpoint por empresa:

```text
https://api.lever.co/v0/postings/{company}?mode=json
```

Campos usados:

- `id`
- `text`
- `hostedUrl`
- `descriptionPlain` / `description`
- `categories.location`
- `createdAt`

## Arbeitnow

Endpoint:

```text
https://www.arbeitnow.com/api/job-board-api
```

Campos usados:

- `slug`
- `title`
- `company_name`
- `url`
- `description`
- `location`
- `remote`
- `created_at`

## Control de calidad

Una oferta no puede ser valida si falta cualquiera de estos campos:

- titulo real del puesto;
- empresa identificable;
- URL HTTP directa a una oferta individual;
- ubicacion o modalidad remota;
- descripcion suficiente para aplicar filtros.

El objetivo es que paginas de navegacion, categorias o busquedas como
`Barcelona`, `Madrid` o `dependiente` queden descartadas siempre.

## Salud de fuentes

Cada ejecucion escribe:

- `data/last_run_report.json`: conteos, logs y errores por fuente.
- `data/source-health.json`: estado resumido por fuente.

Una fuente rota no vacia el sitio: sus errores se registran y las demas fuentes
siguen aportando ofertas. Si todas fallan, el resultado es un estado vacio real,
sin mocks.
