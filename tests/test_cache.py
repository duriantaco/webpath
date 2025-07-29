import time
import tempfile
from pathlib import Path
from unittest.mock import Mock
from webpath.cache import CacheConfig

def test_cache_creation():
    cache = CacheConfig()
    assert cache.ttl == 300
    assert cache.cache_dir.exists()

def test_cache_with_custom_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = CacheConfig(ttl=600, cache_dir=Path(tmpdir))
        assert cache.ttl == 600

def test_cache_miss():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = CacheConfig(cache_dir=Path(tmpdir))
        result = cache.get("get", "https://example.com")
        assert result is None

def test_cache_hit():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = CacheConfig(cache_dir=Path(tmpdir))
        
        response = Mock()
        response.status_code = 200
        response.headers = {"Content-Type": "application/json"}
        response.content = b'{"test": "data"}'
        response.url = "https://example.com"
        
        cache.set("get", "https://example.com", response)
        cached = cache.get("get", "https://example.com")
        
        assert cached["status_code"] == 200
        assert cached["content"] == '{"test": "data"}'

def test_cache_keys_are_different():
    cache = CacheConfig()
    
    key1 = cache._cache_key("get", "https://example.com/users")
    key2 = cache._cache_key("get", "https://example.com/posts")
    
    assert key1 != key2

def test_cache_expires():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = CacheConfig(ttl=1, cache_dir=Path(tmpdir))
        
        response = Mock()
        response.status_code = 200
        response.headers = {}
        response.content = b'test'
        response.url = "https://example.com"
        
        cache.set("get", "https://example.com", response)
        
        assert cache.get("get", "https://example.com") is not None
        
        time.sleep(1.1)
        assert cache.get("get", "https://example.com") is None

def test_sensitive_headers_filtered():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = CacheConfig(cache_dir=Path(tmpdir))
        
        response = Mock()
        response.status_code = 200
        response.headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer secret"
        }
        response.content = b'test'
        response.url = "https://example.com"
        
        cache.set("get", "https://example.com", response)
        cached = cache.get("get", "https://example.com")
        
        assert "Content-Type" in cached["headers"]
        assert "Authorization" not in cached["headers"]