# characters_api Quick Reference

## New Features (Backward Compatible)

### 1. Public/Private Views

**Public View** (no prompts):
```bash
curl "http://localhost:8090/characters/catherine?view=public"
```

**Private View** (with prompts):
```bash
curl "http://localhost:8090/characters/catherine?view=private"
# OR (default)
curl "http://localhost:8090/characters/catherine"
```

### 2. ETag Caching

**First Request**:
```bash
curl -i "http://localhost:8090/characters/catherine"
# Returns: ETag: "abc123..."
```

**Revalidation**:
```bash
curl -i -H 'If-None-Match: "abc123..."' \
  "http://localhost:8090/characters/catherine"
# Returns: 304 Not Modified (if unchanged)
```

### 3. Normalized Prompts

**Access prompts**:
```python
# New way (recommended)
system_prompt = data["prompts"]["system"]
background = data["prompts"]["background"]
matrix_rules = data["prompts"]["matrix_append_rules"]

# Old way (still works)
system_prompt = data["system_prompt"]
background = data["character_background"]
```

## Response Examples

### Public View Response
```json
{
  "id": "catherine",
  "name": "Catherine",
  "nickname": "Cathy",
  "model": "llama3.1:8b",
  "greeting": "Hello!",
  "avatar": "catherine_pfp.jpg",
  "avatar_url": "http://host:8090/avatars/catherine_pfp.jpg",
  "aliases": ["Catherine", "Cathy", "catherine"]
}
```

### Private View Response
```json
{
  "id": "catherine",
  "name": "Catherine",
  "system_prompt": "You are Catherine...",
  "character_background": "Catherine is...",
  "prompts": {
    "system": "You are Catherine...",
    "background": "Catherine is...",
    "matrix_append_rules": "..."
  },
  "aliases": ["Catherine", "Cathy", "catherine"],
  "avatar_url": "http://host:8090/avatars/catherine_pfp.jpg",
  ...
}
```

## Use Cases

### Web UI (Public View)
```javascript
// Fetch character list for dropdown
fetch('/characters')
  .then(r => r.json())
  .then(data => populateDropdown(data.characters));

// Get character details (no prompts)
fetch('/characters/catherine?view=public')
  .then(r => r.json())
  .then(char => displayProfile(char));
```

### AI Service (Private View)
```python
import httpx

# Get full character data with prompts
response = httpx.get(
    "http://api:8090/characters/catherine",
    params={"view": "private"}
)
char = response.json()

# Use normalized prompts
system_prompt = char["prompts"]["system"]
```

### With ETag Caching
```python
import httpx

# First request
response = httpx.get("http://api:8090/characters/catherine")
etag = response.headers.get("etag")
data = response.json()

# Later request with revalidation
response = httpx.get(
    "http://api:8090/characters/catherine",
    headers={"If-None-Match": etag}
)

if response.status_code == 304:
    # Use cached data
    print("Using cached data")
else:
    # Update cache
    etag = response.headers.get("etag")
    data = response.json()
```

## Performance Tips

1. **Always use ETags** - Save ~95% bandwidth
2. **Use public view for UI** - Faster, smaller responses
3. **Cache character list** - Rarely changes
4. **Revalidate on user action** - Not on every page load

## Migration Guide

### No Changes Required
Existing code continues working without modification.

### Optional Improvements

**Before**:
```python
char = get_character("catherine")
prompt = char["system_prompt"]
```

**After** (recommended):
```python
char = get_character("catherine", view="private")
prompt = char["prompts"]["system"]
```

## Testing

**Test public view**:
```bash
curl -s "http://localhost:8090/characters/catherine?view=public" | \
  jq 'has("system_prompt")'
# Should output: false
```

**Test ETag**:
```bash
etag=$(curl -sI "http://localhost:8090/characters" | \
  grep -i etag | awk '{print $2}' | tr -d '\r')
curl -sI -H "If-None-Match: $etag" \
  "http://localhost:8090/characters" | head -1
# Should output: HTTP/1.1 304 Not Modified
```

**Test prompts bundle**:
```bash
curl -s "http://localhost:8090/characters/catherine" | \
  jq '.prompts | keys'
# Should output: ["background", "matrix_append_rules", "system"]
```

## Documentation

- Full details: [API_ENHANCEMENTS.md](API_ENHANCEMENTS.md)
- Implementation: [IMPLEMENTATION_SUMMARY.md](../IMPLEMENTATION_SUMMARY.md)
- Main README: [README.md](../README.md)
