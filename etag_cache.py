"""Content-based ETag generation with file digest caching."""
import hashlib
import json
from pathlib import Path
from typing import Any

# In-memory cache: path -> (mtime_ns, size, ino, dev, digest)
_digest_cache: dict[str, tuple[int, int, int, int, str]] = {}


def _file_digest(path: Path) -> str:
    """Compute SHA-256 digest of file content with metadata-based caching.
    
    :param path: Path to file
    :type path: Path
    :return: SHA-256 hex digest or 'missing' marker
    :rtype: str
    """
    try:
        st = path.stat()
        key = str(path.resolve())
        
        cached = _digest_cache.get(key)
        if cached:
            c_mtime, c_size, c_ino, c_dev, c_digest = cached
            if (st.st_mtime_ns == c_mtime and st.st_size == c_size and 
                st.st_ino == c_ino and st.st_dev == c_dev):
                return c_digest
        
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        _digest_cache[key] = (st.st_mtime_ns, st.st_size, st.st_ino, st.st_dev, digest)
        return digest
    except FileNotFoundError:
        return "missing"


def _safe_resolve(base_dir: Path, filename: str) -> Path | None:
    """Safely resolve file path within base directory.
    
    :param base_dir: Base directory
    :type base_dir: Path
    :param filename: Filename to resolve
    :type filename: str
    :return: Resolved path if safe, None otherwise
    :rtype: Path | None
    """
    if not filename or ".." in filename or "/" in filename or "\\" in filename:
        return None
    return base_dir / filename


def safe_resolve(base_dir: Path, filename: str) -> Path | None:
    """Public API for safe file resolution.
    
    :param base_dir: Base directory
    :type base_dir: Path
    :param filename: Filename to resolve
    :type filename: str
    :return: Resolved path if safe, None otherwise
    :rtype: Path | None
    """
    return _safe_resolve(base_dir, filename)


def compute_etag(char_path: Path, data: dict[str, Any], view: str, 
                 prompt_dir: Path, info_dir: Path, avatar_dir: Path) -> str:
    """Compute content-based ETag for character.
    
    :param char_path: Path to character JSON file
    :type char_path: Path
    :param data: Character configuration data
    :type data: dict[str, Any]
    :param view: View mode ('public' or 'private')
    :type view: str
    :param prompt_dir: Directory containing prompt files
    :type prompt_dir: Path
    :param info_dir: Directory containing info files
    :type info_dir: Path
    :param avatar_dir: Directory containing avatar files
    :type avatar_dir: Path
    :return: ETag value with quotes
    :rtype: str
    """
    manifest = {
        "algo": 2,
        "view": view,
        "json": _file_digest(char_path),
        "files": []
    }
    
    # Avatar (both public and private)
    avatar = data.get("avatar")
    if isinstance(avatar, str) and avatar.strip():
        p = _safe_resolve(avatar_dir, avatar.strip())
        if p:
            manifest["files"].append({
                "field": "avatar",
                "path": avatar.strip(),
                "digest": _file_digest(p)
            })
        else:
            manifest["files"].append({
                "field": "avatar",
                "path": avatar.strip(),
                "digest": "invalid-path"
            })
    
    if view == "private":
        for field, directory in [
            ("system_prompt", prompt_dir),
            ("character_background", info_dir)
        ]:
            val = data.get(field)
            if isinstance(val, str) and val.strip():
                p = _safe_resolve(directory, val.strip())
                if p:
                    manifest["files"].append({
                        "field": field,
                        "path": val.strip(),
                        "digest": _file_digest(p)
                    })
                else:
                    manifest["files"].append({
                        "field": field,
                        "path": val.strip(),
                        "digest": "invalid-path"
                    })
        
        matrix = data.get("matrix")
        if isinstance(matrix, dict):
            ar = matrix.get("append_rules")
            if isinstance(ar, str) and ar.strip():
                p = _safe_resolve(prompt_dir, ar.strip())
                if p:
                    manifest["files"].append({
                        "field": "matrix.append_rules",
                        "path": ar.strip(),
                        "digest": _file_digest(p)
                    })
                else:
                    manifest["files"].append({
                        "field": "matrix.append_rules",
                        "path": ar.strip(),
                        "digest": "invalid-path"
                    })
    
    manifest["files"].sort(key=lambda x: (x["field"], x["path"]))
    canonical = json.dumps(manifest, sort_keys=True, separators=(',', ':'))
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    return f'"{digest}"'


def compute_list_etag(char_dir: Path, avatar_dir: Path) -> str:
    """Compute ETag for character list.
    
    :param char_dir: Directory containing character JSON files
    :type char_dir: Path
    :param avatar_dir: Directory containing avatar files
    :type avatar_dir: Path
    :return: ETag value with quotes
    :rtype: str
    """
    files = sorted(char_dir.glob("*.json"))
    manifest = {"algo": 2, "chars": []}
    
    for f in files:
        entry = {"char": f.name, "json": _file_digest(f)}
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            avatar = data.get("avatar")
            if isinstance(avatar, str) and avatar.strip():
                p = _safe_resolve(avatar_dir, avatar.strip())
                if p:
                    entry["avatar"] = _file_digest(p)
                else:
                    entry["avatar"] = "invalid-path"
        except Exception:
            pass
        manifest["chars"].append(entry)
    
    canonical = json.dumps(manifest, sort_keys=True, separators=(',', ':'))
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    return f'"{digest}"'


def compute_avatar_etag(avatar_path: Path) -> str:
    """Compute content-based ETag for avatar file.
    
    :param avatar_path: Path to avatar file
    :type avatar_path: Path
    :return: ETag value with quotes
    :rtype: str
    """
    return f'"{_file_digest(avatar_path)}"'
