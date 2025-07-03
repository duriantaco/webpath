from __future__ import annotations

from typing import Optional
import hashlib
import json
import time
from pathlib import Path

class CacheConfig:
    def __init__(self, ttl: int = 300, cache_dir: Optional[Path] = None):
        self.ttl = ttl
        self.cache_dir = cache_dir or Path.home() / ".webpath" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _cache_key(self, verb: str, url: str) -> str:
        key_str = f"{verb.upper()}:{url}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _cache_path(self, verb: str, url: str) -> Path:
        key = self._cache_key(verb, url)
        return self.cache_dir / f"{key}.json"
    
    def get(self, verb: str, url: str) -> Optional[dict]:
        cache_path = self._cache_path(verb, url)
        if not cache_path.exists():
            return None
        
        try:
            with cache_path.open('r') as f:
                cached = json.load(f)
            
            if time.time() - cached['timestamp'] > self.ttl:
                cache_path.unlink(missing_ok=True)
                return None
            
            return cached
        except (json.JSONDecodeError, KeyError, OSError):
            cache_path.unlink(missing_ok=True)
            return None
    
    def set(self, verb: str, url: str, response) -> None:
        cache_path = self._cache_path(verb, url)
        
        sensitive_headers = {
            'authorization', 'cookie', 'x-api-key', 'x-auth-token', 
            'authentication', 'proxy-authorization'
        }
        safe_headers = {
            k: v for k, v in response.headers.items() 
            if k.lower() not in sensitive_headers
        }
        
        cached = {
            'timestamp': time.time(),
            'status_code': response.status_code,
            'headers': safe_headers,
            'content': response.content.decode('utf-8', errors='ignore'),
            'url': response.url
        }
        
        try:
            with cache_path.open('w') as f:
                json.dump(cached, f)
        except OSError:
            pass
