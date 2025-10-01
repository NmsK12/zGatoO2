# WolfData DNI API - Detallado

Servidor especializado para consultas detalladas de DNI con 4 imágenes.

## Endpoints

- `GET /dnit?dni=12345678` - Consulta detallada de DNI con 4 imágenes
- `GET /health` - Estado de salud del servicio
- `GET /` - Información del servicio

## Características

- Consulta detallada de DNI con información completa
- 4 imágenes separadas: cara, huellas (2), firma
- Información completa: padres, domicilio, ubigeos, fechas, etc.
- Sistema de cola inteligente
- Manejo de errores y reintentos
- Sin sistema de tokens (ilimitado)

## Instalación

```bash
pip install -r requirements.txt
python api_dnit.py
```

## Variables de Entorno

- `API_ID` - ID de la API de Telegram
- `API_HASH` - Hash de la API de Telegram
- `TARGET_BOT` - Bot objetivo (@OlimpoDataBot)
- `PORT` - Puerto del servidor (default: 8080)
