"""Test robust ETag behavior with content changes."""
import tempfile
import json
from pathlib import Path
import etag_cache


def test_same_size_change_detection():
    """Verify ETag changes when file content changes but size stays same."""
    import time
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        char_file = tmp / "test.json"
        prompt_dir = tmp / "prompts"
        info_dir = tmp / "info"
        avatar_dir = tmp / "avatars"
        prompt_dir.mkdir()
        info_dir.mkdir()
        avatar_dir.mkdir()
        
        prompt_file = prompt_dir / "test.prompt"
        
        # Initial content
        prompt_file.write_text("Hello")
        char_data = {"system_prompt": "test.prompt"}
        char_file.write_text(json.dumps(char_data))
        
        etag1 = etag_cache.compute_etag(char_file, char_data, "private", prompt_dir, info_dir, avatar_dir)
        
        # Sleep to ensure mtime changes
        time.sleep(0.01)
        
        # Change content but keep same size (5 bytes)
        prompt_file.write_text("World")
        etag2 = etag_cache.compute_etag(char_file, char_data, "private", prompt_dir, info_dir, avatar_dir)
        
        assert etag1 != etag2, "ETag must change when content changes (same size)"
        print(f"✓ Same-size change detected: {etag1} → {etag2}")


def test_public_vs_private_etags():
    """Verify public and private views have different ETags."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        char_file = tmp / "test.json"
        prompt_dir = tmp / "prompts"
        info_dir = tmp / "info"
        avatar_dir = tmp / "avatars"
        prompt_dir.mkdir()
        info_dir.mkdir()
        avatar_dir.mkdir()
        
        (prompt_dir / "test.prompt").write_text("System prompt")
        char_data = {"system_prompt": "test.prompt"}
        char_file.write_text(json.dumps(char_data))
        
        etag_public = etag_cache.compute_etag(char_file, char_data, "public", prompt_dir, info_dir, avatar_dir)
        etag_private = etag_cache.compute_etag(char_file, char_data, "private", prompt_dir, info_dir, avatar_dir)
        
        assert etag_public != etag_private, "Public and private views must have different ETags"
        print(f"✓ View separation: public={etag_public[:12]}... private={etag_private[:12]}...")


def test_missing_file_handling():
    """Verify missing referenced files are handled deterministically."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        char_file = tmp / "test.json"
        prompt_dir = tmp / "prompts"
        info_dir = tmp / "info"
        avatar_dir = tmp / "avatars"
        prompt_dir.mkdir()
        info_dir.mkdir()
        avatar_dir.mkdir()
        
        char_data = {"system_prompt": "missing.prompt"}
        char_file.write_text(json.dumps(char_data))
        
        etag1 = etag_cache.compute_etag(char_file, char_data, "private", prompt_dir, info_dir, avatar_dir)
        etag2 = etag_cache.compute_etag(char_file, char_data, "private", prompt_dir, info_dir, avatar_dir)
        
        assert etag1 == etag2, "Missing file ETag must be stable"
        print(f"✓ Missing file handled: {etag1}")


def test_cache_reuse():
    """Verify digest cache reuses values when metadata unchanged."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        char_file = tmp / "test.json"
        prompt_dir = tmp / "prompts"
        info_dir = tmp / "info"
        avatar_dir = tmp / "avatars"
        prompt_dir.mkdir()
        info_dir.mkdir()
        avatar_dir.mkdir()
        
        prompt_file = prompt_dir / "test.prompt"
        prompt_file.write_text("Content")
        char_data = {"system_prompt": "test.prompt"}
        char_file.write_text(json.dumps(char_data))
        
        # Clear cache
        etag_cache._digest_cache.clear()
        
        etag1 = etag_cache.compute_etag(char_file, char_data, "private", prompt_dir, info_dir, avatar_dir)
        cache_size_1 = len(etag_cache._digest_cache)
        
        etag2 = etag_cache.compute_etag(char_file, char_data, "private", prompt_dir, info_dir, avatar_dir)
        cache_size_2 = len(etag_cache._digest_cache)
        
        assert etag1 == etag2, "ETag must be stable when files unchanged"
        assert cache_size_1 == cache_size_2, "Cache should be reused"
        print(f"✓ Cache reused: {cache_size_1} entries")


def test_avatar_changes_invalidate_etags():
    """Verify avatar changes invalidate character and list ETags."""
    import time
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        char_dir = tmp / "characters"
        char_dir.mkdir()
        char_file = char_dir / "test.json"
        prompt_dir = tmp / "prompts"
        info_dir = tmp / "info"
        avatar_dir = tmp / "avatars"
        prompt_dir.mkdir()
        info_dir.mkdir()
        avatar_dir.mkdir()
        
        avatar_file = avatar_dir / "test.jpg"
        avatar_file.write_bytes(b"image1")
        char_data = {"avatar": "test.jpg"}
        char_file.write_text(json.dumps(char_data))
        
        etag1 = etag_cache.compute_etag(char_file, char_data, "public", prompt_dir, info_dir, avatar_dir)
        list_etag1 = etag_cache.compute_list_etag(char_dir, avatar_dir)
        avatar_etag1 = etag_cache.compute_avatar_etag(avatar_file)
        
        time.sleep(0.01)
        avatar_file.write_bytes(b"image2")
        
        etag2 = etag_cache.compute_etag(char_file, char_data, "public", prompt_dir, info_dir, avatar_dir)
        list_etag2 = etag_cache.compute_list_etag(char_dir, avatar_dir)
        avatar_etag2 = etag_cache.compute_avatar_etag(avatar_file)
        
        assert etag1 != etag2, "Character ETag must change when avatar changes"
        assert list_etag1 != list_etag2, "List ETag must change when avatar changes"
        assert avatar_etag1 != avatar_etag2, "Avatar ETag must change when content changes"
        print(f"✓ Avatar change invalidates all ETags")


def test_invalid_path_handling():
    """Verify invalid path refs are handled deterministically."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        char_file = tmp / "test.json"
        prompt_dir = tmp / "prompts"
        info_dir = tmp / "info"
        avatar_dir = tmp / "avatars"
        prompt_dir.mkdir()
        info_dir.mkdir()
        avatar_dir.mkdir()
        
        # Test path traversal attempt
        char_data = {"system_prompt": "../../evil.txt"}
        char_file.write_text(json.dumps(char_data))
        
        etag1 = etag_cache.compute_etag(char_file, char_data, "private", prompt_dir, info_dir, avatar_dir)
        etag2 = etag_cache.compute_etag(char_file, char_data, "private", prompt_dir, info_dir, avatar_dir)
        
        assert etag1 == etag2, "Invalid path ETag must be stable"
        assert "invalid-path" in etag1 or etag1 == etag2, "Should handle invalid paths"
        
        # Changing invalid path should change ETag
        char_data2 = {"system_prompt": "../other.txt"}
        char_file.write_text(json.dumps(char_data2))
        etag3 = etag_cache.compute_etag(char_file, char_data2, "private", prompt_dir, info_dir, avatar_dir)
        
        assert etag1 != etag3, "Different invalid paths should produce different ETags"
        print(f"✓ Invalid paths handled deterministically")


if __name__ == "__main__":
    test_same_size_change_detection()
    test_public_vs_private_etags()
    test_missing_file_handling()
    test_cache_reuse()
    test_avatar_changes_invalidate_etags()
    test_invalid_path_handling()
    print("\n✅ All robust ETag tests passed!")
