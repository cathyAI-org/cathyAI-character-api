"""Test suite for characters_api FastAPI service.

Tests character API endpoints, file resolution, and Docker configuration.
"""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient
import sys
import os

REPO_ROOT = Path(__file__).parent.parent


class TestCharactersAPI:
    """Test suite for characters_api with isolated imports."""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self, monkeypatch):
        """Setup and teardown for each test to ensure clean imports."""
        # Setup
        original_path = sys.path.copy()
        original_modules = set(sys.modules.keys())
        
        os.chdir(REPO_ROOT)
        sys.path.insert(0, str(REPO_ROOT))
        
        # Set environment variables for container/local compatibility
        os.environ["CHAR_DIR"] = str(REPO_ROOT / "characters")
        os.environ["PROMPT_DIR"] = str(REPO_ROOT / "characters" / "system_prompt")
        os.environ["INFO_DIR"] = str(REPO_ROOT / "characters" / "character_info")
        os.environ["AVATAR_DIR"] = str(REPO_ROOT / "public" / "avatars")
        os.environ["CHAR_API_KEY"] = ""
        
        from app import app, CHAR_DIR, PROMPT_DIR, INFO_DIR
        self.app = app
        self.client = TestClient(app)
        self.CHAR_DIR = CHAR_DIR
        self.PROMPT_DIR = PROMPT_DIR
        self.INFO_DIR = INFO_DIR
        
        yield
        
        # Teardown
        sys.path = original_path
        new_modules = set(sys.modules.keys()) - original_modules
        for mod in new_modules:
            if mod.startswith('app'):
                sys.modules.pop(mod, None)

    def test_health_endpoint(self):
        """Test health check endpoint returns ok status."""
        response = self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "char_dir" in data

    def test_list_characters(self):
        """Test listing all characters."""
        response = self.client.get("/characters")
        assert response.status_code == 200
        data = response.json()
        assert "characters" in data
        assert len(data["characters"]) > 0
        
        for char in data["characters"]:
            assert "id" in char
            assert "name" in char
            assert "model" in char
            assert "aliases" in char
            assert isinstance(char["aliases"], list)

    def test_get_character_by_id(self):
        """Test retrieving character with default private view."""
        response = self.client.get("/characters/catherine")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Catherine Ploskaya"
        assert "prompts" in data, "Default should be private view"
        assert "system" in data["prompts"]
        assert len(data["prompts"]["system"]) > 50
        assert "catherine" in [a.lower() for a in data["aliases"]]

    def test_get_nonexistent_character(self):
        """Test 404 response for nonexistent character."""
        response = self.client.get("/characters/nonexistent")
        assert response.status_code == 404

    def test_system_prompt_resolution(self):
        """Test that system prompts are resolved from external files."""
        response = self.client.get("/characters/catherine")
        assert response.status_code == 200
        data = response.json()
        assert data["prompts"]["system"].startswith("You")
        assert len(data["prompts"]["system"]) > 100
        assert data["system_prompt"] == data["prompts"]["system"], "Backward compat field should match"

    def test_character_aliases(self):
        """Test that character aliases include name, nickname, and ID."""
        response = self.client.get("/characters/catherine")
        assert response.status_code == 200
        data = response.json()
        aliases = [a.lower() for a in data["aliases"]]
        assert "catherine" in aliases, "Should include ID"
        assert "catherine ploskaya" in aliases, "Should include full name"

    def test_docker_files_exist(self):
        """Test that Docker configuration files exist."""
        assert (REPO_ROOT / "Dockerfile").exists(), "Dockerfile not found"
        assert (REPO_ROOT / "docker-compose.yaml").exists(), "docker-compose.yaml not found"
        assert (REPO_ROOT / "requirements.txt").exists(), "requirements.txt not found"

    def test_dockerfile_structure(self):
        """Test that Dockerfile has proper structure."""
        dockerfile = (REPO_ROOT / "Dockerfile").read_text()
        assert "FROM python" in dockerfile, "Dockerfile missing Python base image"
        assert "uvicorn" in dockerfile, "Dockerfile missing uvicorn command"
        assert "8090" in dockerfile, "Dockerfile missing port 8090"

    def test_docker_compose_structure(self):
        """Test that docker-compose.yaml has proper structure."""
        compose = (REPO_ROOT / "docker-compose.yaml").read_text()
        assert "characters_api:" in compose, "docker-compose.yaml missing characters_api service"
        assert "8090:8090" in compose, "docker-compose.yaml missing port 8090"

    def test_requirements_has_dependencies(self):
        """Test that requirements.txt has necessary dependencies."""
        content = (REPO_ROOT / "requirements.txt").read_text()
        assert "fastapi" in content, "Missing dependency: fastapi"
        assert "uvicorn" in content, "Missing dependency: uvicorn"

    def test_env_template_exists(self):
        """Test that .env.template exists with required variables."""
        env_template = REPO_ROOT / ".env.template"
        assert env_template.exists(), ".env.template not found"
        content = env_template.read_text()
        assert "CHAR_API_KEY" in content, ".env.template missing CHAR_API_KEY"
        assert "HOST_URL" in content, ".env.template missing HOST_URL"

    def test_app_structure(self):
        """Test that app.py has correct structure."""
        app_file = REPO_ROOT / "app.py"
        content = app_file.read_text()
        assert "FastAPI" in content, "app.py missing FastAPI import"
        assert "def health" in content, "app.py missing health function"
        assert "def list_characters" in content, "app.py missing list_characters function"
        assert "def get_character" in content, "app.py missing get_character function"

    def test_public_view_excludes_prompts(self):
        """Test that public view excludes all prompt text for security."""
        response = self.client.get("/characters/catherine?view=public")
        assert response.status_code == 200
        data = response.json()
        assert "system_prompt" not in data
        assert "character_background" not in data
        assert "prompts" not in data
        assert "name" in data
        assert "avatar_url" in data
        assert "aliases" in data

    def test_private_view_normalized_prompts(self):
        """Test that private view includes normalized prompts bundle."""
        response = self.client.get("/characters/catherine?view=private")
        assert response.status_code == 200
        data = response.json()
        prompts = data["prompts"]
        assert isinstance(prompts, dict)
        assert "system" in prompts
        assert "background" in prompts
        assert isinstance(prompts["system"], str)
        assert len(prompts["system"]) > 50
        assert data["system_prompt"] == prompts["system"], "Backward compat"

    def test_etag_caching_workflow(self):
        """Test complete ETag caching workflow with 304 response."""
        response1 = self.client.get("/characters/catherine")
        assert response1.status_code == 200
        assert "etag" in response1.headers
        etag = response1.headers["etag"]
        assert etag.startswith('"') and etag.endswith('"')
        
        response2 = self.client.get("/characters/catherine", headers={"If-None-Match": etag})
        assert response2.status_code == 304

    def test_etag_on_all_endpoints(self):
        """Test that all endpoints support ETag caching."""
        endpoints = [
            "/characters",
            "/characters/catherine",
            "/avatars/catherine_pfp.jpg"
        ]
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            if response.status_code == 200:
                assert "etag" in response.headers, f"{endpoint} missing ETag"

    def test_api_key_authentication(self):
        """Test API key authentication when configured."""
        import os
        os.environ["CHAR_API_KEY"] = "test_key_123"
        
        # Reimport to pick up new env var
        import importlib
        import sys
        if 'app' in sys.modules:
            importlib.reload(sys.modules['app'])
        from app import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        
        # Without key should fail
        response = client.get("/characters")
        assert response.status_code == 401
        
        # With correct key should succeed
        response = client.get("/characters", headers={"x-api-key": "test_key_123"})
        assert response.status_code == 200
        
        # With wrong key should fail
        response = client.get("/characters", headers={"x-api-key": "wrong_key"})
        assert response.status_code == 401
        
        # Reset
        os.environ["CHAR_API_KEY"] = ""

    def test_safe_filename_validation(self):
        """Test that unsafe filenames are rejected."""
        unsafe_names = [
            "../etc/passwd",
            "..\\windows\\system32",
            "file/with/slash",
            "file\\with\\backslash"
        ]
        for name in unsafe_names:
            response = self.client.get(f"/avatars/{name}")
            # Should return 400 for invalid filename or 404 if path traversal blocked
            assert response.status_code in [400, 404], f"Should reject unsafe filename: {name}"

    def test_character_background_resolution(self):
        """Test that character background is resolved from external files."""
        response = self.client.get("/characters/catherine")
        assert response.status_code == 200
        data = response.json()
        assert "character_background" in data
        assert "prompts" in data
        assert "background" in data["prompts"]
        assert data["character_background"] == data["prompts"]["background"]
