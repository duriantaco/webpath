
import requests_mock
from webpath import WebPath
import pytest

def test_json_parsing_error_fallback():
    with requests_mock.Mocker() as m:
        m.get("https://api.com/broken", text="{invalid json}")
        
        resp = WebPath("https://api.com/broken").get()
        # json_data should fall back to empty dict
        assert resp.json_data == {}
        
        with pytest.raises(Exception):
            resp.json()

def test_response_key_error_handling():
    """handle missing keys in JSON responses"""
    with requests_mock.Mocker() as m:
        m.get("https://api.com/data", json={"exists": "value"})
        
        resp = WebPath("https://api.com/data").get()
        
        assert resp / "exists" == "value"
        
        with pytest.raises(KeyError):
            resp / "missing"

def test_http_error_messages():
    """should provide helpful error messages"""
    with requests_mock.Mocker() as m:
        m.get("https://api.com/401", status_code=401, json={"error": "Invalid token"})
        m.get("https://api.com/429", status_code=429, headers={"Retry-After": "60"})
        
        with pytest.raises(Exception, match="Authentication failed.*Invalid token"):
            WebPath("https://api.com/401").get()
        
        with pytest.raises(Exception, match="Rate limited.*60 seconds"):
            WebPath("https://api.com/429").get()
