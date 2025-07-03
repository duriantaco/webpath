from __future__ import annotations

import functools
from typing import Any, Dict, List, Callable, Optional
import threading
from collections import OrderedDict
from pathlib import Path
from urllib.parse import quote, urlencode, urlunsplit, parse_qsl, urlsplit

from webpath._http import http_request, session_cm, aget_async
from webpath.downloads import download_file
from webpath.cache import CacheConfig

_IDNA_CACHE: OrderedDict[str, str] = OrderedDict()
_IDNA_CACHE_LOCK = threading.RLock()
_IDNA_CACHE_MAX_SIZE = 1000
_HTTP_VERBS = ("get", "post", "put", "patch", "delete", "head", "options")

def _idna(netloc: str) -> str:
    with _IDNA_CACHE_LOCK:
        if netloc in _IDNA_CACHE:
            _IDNA_CACHE.move_to_end(netloc)
            return _IDNA_CACHE[netloc]
        
        try:
            ascii_netloc = netloc.encode("idna").decode("ascii")
        except UnicodeError:
            ascii_netloc = netloc
        
        if len(_IDNA_CACHE) >= _IDNA_CACHE_MAX_SIZE:
            _IDNA_CACHE.popitem(last=False)
        
        _IDNA_CACHE[netloc] = ascii_netloc
        return ascii_netloc

class WebPath:
    __slots__ = ("_url", "_parts", "_trailing_slash", "_cache", "_cache_config", "_allow_auto_follow", "_enable_logging", "_rate_limit", "_last_request_time")
    def __init__(self, url: str | "WebPath") -> None:
        self._url = str(url).strip()
        
        if not self._url:
            raise ValueError("URL cannot be empty")
        
        self._parts = urlsplit(self._url)
        
        if not self._parts.scheme:
            raise ValueError(f"URL must include scheme (http/https): {self._url}")
        if self._parts.scheme not in ('http', 'https'):
            raise ValueError(f"Only http/https schemes supported: {self._parts.scheme}")
        if not self._parts.netloc:
            raise ValueError(f"URL must include hostname: {self._url}")
        
        self._trailing_slash = self._url.endswith("/") and not self._parts.path.endswith("/")
        self._cache = {}
        self._cache_config = None
        self._allow_auto_follow = False
        self._enable_logging = False
        self._rate_limit = None
        self._last_request_time = 0

    def __str__(self) -> str:
        return self._url

    def __repr__(self) -> str:
        return f"WebPath({self._url!r})"

    def __eq__(self, other) -> bool:
        """Enable comparison with strings and other WebPaths"""
        if isinstance(other, WebPath):
            return self._url == other._url
        elif isinstance(other, str):
            return self._url == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._url)

    def __bool__(self) -> bool:
        return bool(self._url)

    # internal helper
    def _memo(self, key: str, factory: Callable[[], Any]):
        cache = self._cache
        if key not in cache:
            cache[key] = factory()
        return cache[key]

    @property
    def query(self) -> Dict[str, List[str] | str]:
        return self._memo(
            "query",
            lambda: dict(parse_qsl(self._parts.query, keep_blank_values=True)),
        )

    @property
    def scheme(self) -> str:
        return self._parts.scheme

    @property
    def netloc(self) -> str:     # pragma: no skylos
        return self._parts.netloc

    @property
    def host(self) -> str:     # pragma: no skylos
        return _idna(self._parts.netloc.split("@")[-1].split(":")[0])

    @property
    def port(self) -> str | None:     # pragma: no skylos
        if ":" in self._parts.netloc:
            return self._parts.netloc.rsplit(":", 1)[1]
        return None

    @property
    def path(self) -> str:
        return self._parts.path

    def __truediv__(self, other: str | int | "WebPath") -> "WebPath":
        seg = quote(str(other).lstrip("/"))
        new_path = self._parts.path.rstrip("/") + "/" + seg if self._parts.path else "/" + seg
        return self._replace(path=new_path)

    @property
    def parent(self) -> "WebPath":     # pragma: no skylos
        parts = self._parts.path.rstrip("/").split("/")
        parent_path = "/".join(parts[:-1]) or "/"
        return self._replace(path=parent_path)

    @property
    def name(self) -> str:
        return self._parts.path.rstrip("/").split("/")[-1]

    @property
    def suffix(self) -> str:     # pragma: no skylos
        dot = self.name.rfind(".")
        return self.name[dot:] if dot != -1 else ""

    def ensure_trailing_slash(self) -> "WebPath":     # pragma: no skylos
        return self if self._url.endswith("/") else WebPath(self._url + "/")

    def with_query(self, **params: Any) -> "WebPath":     # pragma: no skylos
        merged = dict(self.query)
        
        for key, value in params.items():
            if isinstance(value, (list, tuple)):
                merged[key] = list(value)
            elif value is None:
                merged.pop(key, None)
            else:
                merged[key] = value
        
        q_string = urlencode(merged, doseq=True, safe=":/")
        return self._replace(query=q_string)

    def without_query(self) -> "WebPath":     # pragma: no skylos
        return self._replace(query="")

    def with_fragment(self, tag: str) -> "WebPath":     # pragma: no skylos
        return self._replace(fragment=quote(tag))

    def __getattr__(self, item: str):
        if item in _HTTP_VERBS:
            return functools.partial(http_request, item, self)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{item}'")

    def with_cache(self, ttl: int = 300, cache_dir: Optional[Path] = None) -> "WebPath":     # pragma: no skylos
        new_path = WebPath(self._url)
        new_path._cache_config = CacheConfig(ttl, cache_dir)
        return new_path
  
    def with_logging(self, enabled: bool = True) -> "WebPath":     # pragma: no skylos
        new_path = WebPath(self._url)
        new_path._cache_config = self._cache_config
        new_path._allow_auto_follow = self._allow_auto_follow
        new_path._enable_logging = enabled
        return new_path

    def with_rate_limit(self, requests_per_second: float = 1.0) -> "WebPath":
        new_path = WebPath(self._url)
        new_path._cache_config = self._cache_config
        new_path._allow_auto_follow = self._allow_auto_follow
        new_path._enable_logging = self._enable_logging
        new_path._rate_limit = requests_per_second
        new_path._last_request_time = 0
        return new_path
    
    def session(self, **kw):     # pragma: no skylos
        return session_cm(self, **kw)

    async def aget(self, *a, **kw):    # pragma: no skylos
        return await aget_async(self, *a, **kw)

    def download(self, dest, **kw):
        return download_file(self, dest, **kw)

    def _replace(self, **patch) -> "WebPath":
        data = self._parts._asdict() | patch
        url = urlunsplit(tuple(data[k] for k in ("scheme", "netloc", "path", "query", "fragment")))
        if self._trailing_slash and not url.endswith("/"):
            url += "/"
        return WebPath(url)

    def __iter__(self):
        return iter(self._parts.path.strip("/").split("/"))