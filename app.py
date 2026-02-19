from fastapi import FastAPI, HTTPException, Request, Query, Response
from fastapi.responses import FileResponse
from pathlib import Path
import json
import os
import hashlib
from typing import Any, Literal

app = FastAPI(title="cathyAI Characters API", version="1.0.0")

# ---- Paths for your new repo layout ----
REPO_ROOT = Path(__file__).resolve().parent

CHAR_DIR = Path(os.getenv("CHAR_DIR", "/app/characters"))
PROMPT_DIR = Path(os.getenv("PROMPT_DIR", str(CHAR_DIR / "system_prompt")))
INFO_DIR = Path(os.getenv("INFO_DIR", str(CHAR_DIR / "character_info")))
AVATAR_DIR = Path(os.getenv("AVATAR_DIR", "/app/public/avatars"))

API_KEY = os.getenv("CHAR_API_KEY", "")
HOST_URL = os.getenv("HOST_URL", "").rstrip("/")  # e.g. http://192.168.1.58:8090


def require_auth(req: Request) -> None:
    """Validate API key authentication if configured.
    
    :param req: FastAPI request object containing headers
    :type req: Request
    :raises HTTPException: When API key is required but missing or invalid
    """
    if not API_KEY:
        return
    if req.headers.get("x-api-key", "") != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


def safe_filename(name: str) -> bool:
    """Check if filename is safe for file system access.
    
    :param name: Filename to validate
    :type name: str
    :return: True if filename is safe, False otherwise
    :rtype: bool
    """
    return bool(name) and "/" not in name and "\\" not in name and ".." not in name


def read_json(path: Path) -> dict[str, Any]:
    """Read and parse JSON file.
    
    :param path: Path to JSON file
    :type path: Path
    :return: Parsed JSON data
    :rtype: dict[str, Any]
    :raises HTTPException: When file cannot be read or parsed
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse {path.name}: {e}")


def maybe_resolve_file(value: Any, directory: Path) -> str:
    """Resolve file content or return inline text.
    
    If value is a string and matches a file in directory, load it.
    Otherwise treat it as inline text.
    
    :param value: File path or inline text content
    :type value: Any
    :param directory: Directory to search for files
    :type directory: Path
    :return: File content or original value as string
    :rtype: str
    """
    if not isinstance(value, str) or not value.strip():
        return ""
    candidate = directory / value.strip()
    if candidate.exists() and candidate.is_file():
        return candidate.read_text(encoding="utf-8").strip()
    return value.strip()


def dedupe_case_insensitive(items: list[str]) -> list[str]:
    """Remove case-insensitive duplicates from string list.
    
    :param items: List of strings to deduplicate
    :type items: list[str]
    :return: List with duplicates removed (case-insensitive)
    :rtype: list[str]
    """
    seen: set[str] = set()
    out: list[str] = []
    for s in items:
        key = s.lower()
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out


def build_aliases(data: dict[str, Any], char_id: str) -> list[str]:
    """Build list of character aliases from character data.
    
    :param data: Character configuration data
    :type data: dict[str, Any]
    :param char_id: Character identifier
    :type char_id: str
    :return: List of character aliases
    :rtype: list[str]
    """
    aliases: list[str] = []

    for k in ("name", "nickname"):
        v = data.get(k)
        if isinstance(v, str) and v.strip():
            aliases.append(v.strip())

    # Optional list fields you might add later
    for k in ("nicknames", "aliases"):
        v = data.get(k)
        if isinstance(v, list):
            aliases.extend([x.strip() for x in v if isinstance(x, str) and x.strip()])

    # Matrix-specific block
    matrix = data.get("matrix")
    if isinstance(matrix, dict):
        v = matrix.get("aliases")
        if isinstance(v, list):
            aliases.extend([x.strip() for x in v if isinstance(x, str) and x.strip()])

    # Always include the id
    aliases.append(char_id)

    return dedupe_case_insensitive(aliases)


def attach_avatar_url(data: dict[str, Any]) -> None:
    """Add avatar_url field to character data.
    
    :param data: Character data dictionary to modify
    :type data: dict[str, Any]
    """
    avatar = data.get("avatar")
    if isinstance(avatar, str) and avatar.strip():
        if HOST_URL:
            data["avatar_url"] = f"{HOST_URL}/avatars/{avatar.strip()}"
        else:
            data["avatar_url"] = f"/avatars/{avatar.strip()}"
    else:
        data["avatar_url"] = None


def file_fingerprint(path: Path) -> str:
    """Generate stable fingerprint based on file mtime and size.
    
    :param path: Path to file
    :type path: Path
    :return: Fingerprint string
    :rtype: str
    """
    try:
        st = path.stat()
        return f"{path.name}:{int(st.st_mtime)}:{st.st_size}"
    except FileNotFoundError:
        return f"{path.name}:missing"


def compute_character_etag(char_path: Path, data: dict[str, Any]) -> str:
    """Compute ETag for character including referenced files.
    
    :param char_path: Path to character JSON file
    :type char_path: Path
    :param data: Character configuration data
    :type data: dict[str, Any]
    :return: ETag value with quotes
    :rtype: str
    """
    parts = [file_fingerprint(char_path)]

    sp = data.get("system_prompt")
    if isinstance(sp, str) and sp.strip():
        candidate = PROMPT_DIR / sp.strip()
        if candidate.exists() and candidate.is_file():
            parts.append(file_fingerprint(candidate))

    bg = data.get("character_background")
    if isinstance(bg, str) and bg.strip():
        candidate = INFO_DIR / bg.strip()
        if candidate.exists() and candidate.is_file():
            parts.append(file_fingerprint(candidate))

    matrix = data.get("matrix")
    if isinstance(matrix, dict):
        ar = matrix.get("append_rules")
        if isinstance(ar, str) and ar.strip():
            candidate = PROMPT_DIR / ar.strip()
            if candidate.exists() and candidate.is_file():
                parts.append(file_fingerprint(candidate))

    raw = "|".join(parts).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    return f'"{digest}"'


def compute_char_list_etag() -> str:
    """Compute ETag for character list based on all JSON files.
    
    :return: ETag value with quotes
    :rtype: str
    """
    parts = []
    for f in sorted(CHAR_DIR.glob("*.json")):
        parts.append(file_fingerprint(f))
    raw = "|".join(parts).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    return f'"{digest}"'


def resolve_character(data: dict[str, Any], char_id: str) -> dict[str, Any]:
    """Resolve character data with file content and computed fields.
    
    :param data: Raw character configuration data
    :type data: dict[str, Any]
    :param char_id: Character identifier
    :type char_id: str
    :return: Resolved character data with file content loaded
    :rtype: dict[str, Any]
    """
    prompts: dict[str, str] = {}

    system = maybe_resolve_file(data.get("system_prompt"), PROMPT_DIR)
    background = maybe_resolve_file(data.get("character_background"), INFO_DIR)

    prompts["system"] = system
    prompts["background"] = background

    data["system_prompt"] = system
    data["character_background"] = background

    matrix = data.get("matrix")
    if isinstance(matrix, dict):
        append_rules = matrix.get("append_rules")
        if isinstance(append_rules, str) and append_rules.strip():
            art = maybe_resolve_file(append_rules, PROMPT_DIR)
            prompts["matrix_append_rules"] = art
            matrix["append_rules_text"] = art
        data["matrix"] = matrix

    data["prompts"] = prompts
    data["aliases"] = build_aliases(data, char_id)
    attach_avatar_url(data)
    data.pop("secrets", None)

    return data


@app.get("/health")
def health():
    """Health check endpoint.
    
    :return: Health status and configuration paths
    :rtype: dict[str, Any]
    """
    return {
        "ok": True,
        "char_dir": str(CHAR_DIR),
        "prompt_dir": str(PROMPT_DIR),
        "info_dir": str(INFO_DIR),
        "avatar_dir": str(AVATAR_DIR),
    }


@app.get("/characters")
def list_characters(req: Request, response: Response):
    """List all available characters.
    
    :param req: FastAPI request object
    :type req: Request
    :param response: FastAPI response object
    :type response: Response
    :return: Dictionary containing list of characters
    :rtype: dict[str, Any]
    :raises HTTPException: When authentication fails or character directory not found
    """
    require_auth(req)

    if not CHAR_DIR.exists():
        raise HTTPException(500, f"Character directory not found: {CHAR_DIR}")

    etag = compute_char_list_etag()
    response.headers["ETag"] = etag

    inm = req.headers.get("if-none-match")
    if inm and inm.strip() == etag:
        response.status_code = 304
        return None

    out: list[dict[str, Any]] = []
    for f in sorted(CHAR_DIR.glob("*.json")):
        char_id = f.stem
        data = read_json(f)

        # lightweight list view (no resolved full prompt needed, but we keep aliases + avatar_url)
        item = {
            "id": char_id,
            "name": data.get("name") or char_id,
            "nickname": data.get("nickname"),
            "model": data.get("model"),
            "greeting": data.get("greeting"),
            "avatar": data.get("avatar"),
        }
        # include aliases and avatar_url for UX
        item["aliases"] = build_aliases(data, char_id)

        # avatar_url
        avatar = data.get("avatar")
        if isinstance(avatar, str) and avatar.strip():
            item["avatar_url"] = f"{HOST_URL}/avatars/{avatar.strip()}" if HOST_URL else f"/avatars/{avatar.strip()}"
        else:
            item["avatar_url"] = None

        out.append(item)

    return {"characters": out}


@app.get("/characters/{char_id}")
def get_character(
    char_id: str,
    req: Request,
    response: Response,
    view: Literal["public", "private"] = Query("private")
):
    """Get detailed character information.
    
    :param char_id: Character identifier
    :type char_id: str
    :param req: FastAPI request object
    :type req: Request
    :param response: FastAPI response object
    :type response: Response
    :param view: View mode (public excludes prompts, private includes all)
    :type view: Literal["public", "private"]
    :return: Resolved character data
    :rtype: dict[str, Any]
    :raises HTTPException: When authentication fails or character not found
    """
    require_auth(req)

    f = CHAR_DIR / f"{char_id}.json"
    if not f.exists() or not f.is_file():
        raise HTTPException(404, "Character not found")

    data = read_json(f)

    etag = compute_character_etag(f, data)
    response.headers["ETag"] = etag

    inm = req.headers.get("if-none-match")
    if inm and inm.strip() == etag:
        response.status_code = 304
        return None

    public_item = {
        "id": char_id,
        "name": data.get("name") or char_id,
        "nickname": data.get("nickname"),
        "model": data.get("model"),
        "greeting": data.get("greeting"),
        "avatar": data.get("avatar"),
        "aliases": build_aliases(data, char_id),
    }

    avatar = data.get("avatar")
    if isinstance(avatar, str) and avatar.strip():
        public_item["avatar_url"] = f"{HOST_URL}/avatars/{avatar.strip()}" if HOST_URL else f"/avatars/{avatar.strip()}"
    else:
        public_item["avatar_url"] = None

    if view == "public":
        return public_item

    resolved = resolve_character(data, char_id)
    resolved["id"] = char_id
    return resolved


@app.get("/avatars/{filename}")
def get_avatar(filename: str, req: Request, response: Response):
    """Serve character avatar image (public endpoint).
    
    :param filename: Avatar filename
    :type filename: str
    :param req: FastAPI request object
    :type req: Request
    :param response: FastAPI response object
    :type response: Response
    :return: Avatar image file response
    :rtype: FileResponse
    :raises HTTPException: When filename invalid or file not found
    """
    if not safe_filename(filename):
        raise HTTPException(400, "Invalid filename")

    p = AVATAR_DIR / filename
    if not p.exists() or not p.is_file():
        raise HTTPException(404, "Avatar not found")

    etag = f'"{file_fingerprint(p)}"'
    response.headers["ETag"] = etag

    inm = req.headers.get("if-none-match")
    if inm and inm.strip() == etag:
        response.status_code = 304
        return None

    return FileResponse(str(p))
