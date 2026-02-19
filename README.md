# cathyAI-character-api

FastAPI service for managing and serving character configurations, prompts, and avatars.

## Features

- RESTful API for character data
- File-based prompt resolution
- Avatar serving with ETag caching
- Optional API key authentication
- Docker support

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
uvicorn app:app --host 0.0.0.0 --port 8090

# Or with Docker
docker-compose up --build
```

## API Endpoints

- `GET /health` - Health check
- `GET /characters` - List all characters
- `GET /characters/{char_id}?view=private|public` - Get character details
- `GET /avatars/{filename}` - Serve avatar images

## Configuration

Environment variables (see `.env.template`):

- `CHAR_API_KEY` - Optional API key for authentication
- `HOST_URL` - Base URL for avatar links (e.g., `http://192.168.1.58:8090`)
- `CHAR_DIR` - Character JSON directory (default: `/app/characters`)
- `PROMPT_DIR` - System prompts directory (default: `/app/characters/system_prompt`)
- `INFO_DIR` - Character info directory (default: `/app/characters/character_info`)
- `AVATAR_DIR` - Avatar images directory (default: `/app/public/avatars`)

## Testing

```bash
pytest tests/
```
