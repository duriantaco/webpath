
import requests_mock
from webpath import WebPath

def test_ssrf_protection_disabled_by_default():
    with requests_mock.Mocker() as m:
        m.get("https://api.example.com/data", json={
            "next_url": "http://localhost:8080/internal"
        })
        
        resp = WebPath("https://api.example.com/data").get()
        result = resp / "next_url"
        assert result == "http://localhost:8080/internal"
        assert m.call_count == 1

def test_ssrf_protection_blocks_localhost():
    with requests_mock.Mocker() as m:
        m.get("https://api.example.com/data", json={
            "redirect": "http://127.0.0.1:6379/evil"
        })
        
        resp = WebPath("https://api.example.com/data").get()
        # Tneed to add _allow_auto_follow to WebPath.. for now test that it returns string instead of following
        result = resp / "redirect"
        assert result == "http://127.0.0.1:6379/evil"

def test_cache_excludes_sensitive_headers():
    """Cache should not store sensitive authentication headers"""
    import tempfile
    from pathlib import Path
    
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = Path(tmpdir)
        
        with requests_mock.Mocker() as m:
            m.get("https://api.example.com/secret", 
                  text="sensitive data",
                  headers={
                      "Authorization": "Bearer secret-token",
                      "X-API-Key": "api-key-123",
                      "Content-Type": "application/json"
                  })
            
            url = WebPath("https://api.example.com/secret").with_cache(cache_dir=cache_dir)
            resp = url.get()
            
            cache_files = list(cache_dir.glob("*.json"))
            assert len(cache_files) == 1
            
            import json
            with cache_files[0].open() as f:
                cached = json.load(f)
            
            headers = cached["headers"]
            assert "authorization" not in headers
            assert "x-api-key" not in headers
            assert "Content-Type" in headers