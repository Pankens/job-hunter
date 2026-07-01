# Fuentes de ofertas

## InfoJobs

InfoJobs es la primera fuente real del proyecto. La integración usa exclusivamente
la API oficial de búsqueda de ofertas; no realiza scraping.

Documentación oficial:

- [Portal para desarrolladores](https://developer.infojobs.net/)
- [Guía de inicio](https://developer.infojobs.net/documentation/quick-start/index.xhtml)
- [Autenticación de aplicaciones](https://developer.infojobs.net/documentation/app-auth/index.xhtml)
- [Búsqueda de ofertas](https://developer.infojobs.net/documentation/operation/offer-list-9.xhtml)

### Obtener credenciales

1. Inicia sesión en el portal de desarrolladores de InfoJobs.
2. Registra una aplicación.
3. Copia el **Client ID** y el **Client secret** de la aplicación.

La búsqueda de ofertas es una operación pública respecto al usuario: no necesita
OAuth ni acceso al CV. InfoJobs sí exige que cada petición identifique la aplicación
mediante autenticación HTTP Basic.

Nunca uses el email o la contraseña de candidato y nunca guardes secretos en Git.

### Configuración local

Crea un archivo `.env` únicamente si tu terminal o herramienta lo carga. El script
usa variables de entorno y no lee el archivo por sí mismo:

```text
INFOJOBS_CLIENT_ID=tu_client_id
INFOJOBS_CLIENT_SECRET=tu_client_secret
```

En PowerShell también pueden definirse para la sesión actual:

```powershell
$env:INFOJOBS_CLIENT_ID = "tu_client_id"
$env:INFOJOBS_CLIENT_SECRET = "tu_client_secret"
python scripts/export_jobs.py
```

`.env` está ignorado por Git. `.env.example` solo contiene nombres de variables.

### Configuración en GitHub Actions

En el repositorio, abre **Settings → Secrets and variables → Actions** y crea estos
repository secrets:

- `INFOJOBS_CLIENT_ID`
- `INFOJOBS_CLIENT_SECRET`

`update-jobs.yml` los expone únicamente al proceso que ejecuta el exportador.

### Búsquedas y límites

`config/searches.json` define:

- Valencia, Paterna y Burjassot.
- Una búsqueda general sin palabra clave.
- Una búsqueda de programación, desarrollo web e IT.
- Una búsqueda con Java, HTML, CSS, SCSS, Figma, JavaScript, TypeScript, Vue,
  Angular, MongoDB y MySQL.
- Ofertas de los últimos siete días, 50 resultados por página y un máximo
  configurable de páginas.

Los resultados repetidos entre búsquedas se consolidan primero por ID de InfoJobs y
después pasan por la deduplicación general del pipeline.

El listado oficial proporciona requisitos mínimos, pero no siempre una descripción
completa ni salario. Esos campos quedan vacíos cuando no existen y la oferta recibe
un `warning`; el pipeline no falla por datos opcionales ausentes.

### Fallback

Si faltan credenciales, InfoJobs devuelve un error, hay un timeout, el JSON no tiene
el formato esperado o no se recupera ninguna oferta, el exportador usa
`data/mock/source_jobs.json`. El resultado indica:

```json
{
  "mode": "mock-fallback",
  "sourceStatus": {
    "requested": "infojobs",
    "used": "mock",
    "fallback": true,
    "warning": "..."
  }
}
```

Esto mantiene GitHub Pages operativa incluso durante una incidencia de la fuente.

## Indeed

No implementado. Permanece deshabilitado en `config/searches.json`.

## LinkedIn

No se implementa scraping ni importación manual.
