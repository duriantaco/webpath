from __future__ import annotations
import requests
import threading
from collections import OrderedDict
from urllib.parse import quote, urlencode, urlunsplit, parse_qsl, urlsplit
from webpath._http import http_request, session_cm, aget_async
from webpath.downloads import download_file
from webpath.cache import CacheConfig

_IDNA_CACHE: OrderedDict[str, str] = OrderedDict()
_IDNA_CACHE_LOCK = threading.RLock()
_IDNA_CACHE_MAX_SIZE = 1000
_HTTP_VERBS = ("get", "post", "put", "patch", "delete", "head", "options")

def _idna(netloc: str):
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

class Client:
    
    def __init__(
        self, 
        base_url,
        *,
        headers=None,
        cache_ttl=None,
        cache_dir=None,
        retries=None,
        backoff=None,
        jitter=None,
        rate_limit=None,
        enable_logging=False,
        auto_follow=False,
        timeout=None
    ):
        self.base_url = WebPath(base_url)
        
        self.session = requests.Session()
        if headers:
            self.session.headers.update(headers)
        
        if retries:
            from webpath._http import _build_retry_adapter
            adapter = _build_retry_adapter(retries, backoff or 0.3, jitter or 0.0)
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)
        
        self._config = {
            "headers": headers or {},
            "cache_ttl": cache_ttl,
            "cache_dir": cache_dir,
            "retries": retries,
            "backoff": backoff,
            "jitter": jitter,
            "rate_limit": rate_limit,
            "enable_logging": enable_logging,
            "auto_follow": auto_follow,
            "timeout": timeout,
            "session": self.session
        }
    
    def path(self, *segments):
        final_path = self.base_url
        for segment in segments:
            final_path = final_path / segment
        
        return final_path.apply_config(self._config)
    
    def __truediv__(self, segment):
        return self.path(segment)
    
    def get(self, *segments, **params):
        return self.path(*segments).with_query(**params).get()
    
    def post(self, *segments, **kwargs):
        return self.path(*segments).post(**kwargs)
    
    def put(self, *segments, **kwargs):
        return self.path(*segments).put(**kwargs)
    
    def patch(self, *segments, **kwargs):
        return self.path(*segments).patch(**kwargs)
    
    def delete(self, *segments, **kwargs):
        return self.path(*segments).delete(**kwargs)
    
    def session_cm(self, **kw):
        return self.base_url.apply_config(self._config).session(**kw)
    
    def with_config(self, **updates):
        new_config = self._config.copy()
        
        if "headers" in updates:
            new_config["headers"] = {**new_config.get("headers", {}), **updates.pop("headers")}
        
        new_config.update(updates)
        
        new_client = Client(
            str(self.base_url),
            headers=new_config.get("headers"),
            cache_ttl=new_config.get("cache_ttl"),
            cache_dir=new_config.get("cache_dir"),
            retries=new_config.get("retries"),
            backoff=new_config.get("backoff"),
            jitter=new_config.get("jitter"),
            rate_limit=new_config.get("rate_limit"),
            enable_logging=new_config.get("enable_logging", False),
            auto_follow=new_config.get("auto_follow", False),
            timeout=new_config.get("timeout")
        )
        
        new_client.session.cookies.update(self.session.cookies)
        
        return new_client
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def close(self):
        if self.session:
            self.session.close()

class WebPath:
    __slots__ = (
        "_url", "_parts", "_trailing_slash", "_cache", "_cache_config", 
        "_allow_auto_follow", "_enable_logging", "_rate_limit", "_last_request_time",
        "_default_headers", "_retries", "_backoff", "_jitter", "_timeout", "_session"
    )
    
    def __init__(self, url):
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
        self._default_headers = {}
        self._retries = None
        self._backoff = 0.3
        self._jitter = 0.0
        self._timeout = None
        self._session = None

    def __str__(self):
        return self._url

    def __repr__(self):
        return f"WebPath({self._url!r})"

    def __eq__(self, other):
        if isinstance(other, WebPath):
            return self._url == other._url
        elif isinstance(other, str):
            return self._url == other
        return NotImplemented

    def __hash__(self):
        return hash(self._url)

    def __bool__(self):
        return bool(self._url)

    def _memo(self, key, factory):
        cache = self._cache
        if key not in cache:
            cache[key] = factory()
        return cache[key]

    @property
    def query(self):
        return self._memo(
            "query",
            lambda: dict(parse_qsl(self._parts.query, keep_blank_values=True)),
        )

    @property
    def scheme(self):
        return self._parts.scheme

    @property
    def netloc(self):     # pragma: no skylos
        return self._parts.netloc

    @property
    def host(self):     # pragma: no skylos
        return _idna(self._parts.netloc.split("@")[-1].split(":")[0])

    @property
    def port(self):     # pragma: no skylos
        if ":" in self._parts.netloc:
            return self._parts.netloc.rsplit(":", 1)[1]
        return None

    @property
    def path(self):
        return self._parts.path

    def __truediv__(self, other):
        seg = quote(str(other).lstrip("/"))
        if self._parts.path:
            new_path = self._parts.path.rstrip("/") + "/" + seg
        else:
            new_path = "/" + seg
        return self._replace(path=new_path)

    @property
    def parent(self):     # pragma: no skylos
        parts = self._parts.path.rstrip("/").split("/")
        parent_path = "/".join(parts[:-1]) or "/"
        return self._replace(path=parent_path)

    @property
    def name(self):
        path = self._parts.path.rstrip("/")
        return path.split("/")[-1]

    @property
    def suffix(self):     # pragma: no skylos
        dot = self.name.rfind(".")
        if dot == -1:
            return ""
        return self.name[dot:]

    def ensure_trailing_slash(self):
        if self._url.endswith("/"):
            return self
        return WebPath(self._url + "/")

    def with_query(self, **params):     # pragma: no skylos
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

    def without_query(self):     # pragma: no skylos
        return self._replace(query="")

    def with_fragment(self, tag):     # pragma: no skylos
        return self._replace(fragment=quote(tag))

    def apply_config(self, config):
        updates = {}
        
        if config.get("headers"):
            new_headers = self._default_headers.copy()
            new_headers.update(config["headers"])
            updates["_default_headers"] = new_headers
        
        if "cache_ttl" in config:
            updates["_cache_config"] = CacheConfig(config["cache_ttl"], config.get("cache_dir"))
        
        if "session" in config:
            updates["_session"] = config["session"]
        
        for attr, key in [
            ("_retries", "retries"), ("_backoff", "backoff"), ("_jitter", "jitter"),
            ("_rate_limit", "rate_limit"), ("_enable_logging", "enable_logging"),
            ("_timeout", "timeout")
        ]:
            if key in config:
                updates[attr] = config[key]
        
        if "auto_follow" in config:
            updates["_allow_auto_follow"] = config["auto_follow"]
        
        return self._clone(**updates)

    def __getattr__(self, item):
        if item in _HTTP_VERBS:
            def request_method(*args, **kwargs):
                kwargs.setdefault("retries", self._retries)
                kwargs.setdefault("backoff", self._backoff)
                kwargs.setdefault("jitter", self._jitter)
                kwargs.setdefault("timeout", self._timeout)
                
                kwargs["session"] = self._session
                
                headers = {**self._default_headers, **kwargs.get("headers", {})}
                if headers:
                    kwargs["headers"] = headers
                
                return http_request(item, self, *args, **kwargs)
            return request_method
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{item}'")

    def with_cache(self, ttl=300, cache_dir=None):     # pragma: no skylos
        return self._clone(_cache_config=CacheConfig(ttl, cache_dir))
  
    def with_logging(self, enabled=True):     # pragma: no skylos
        return self._clone(_enable_logging=enabled)

    def with_rate_limit(self, requests_per_second=1.0):
        return self._clone(_rate_limit=requests_per_second, _last_request_time=0)

    def _clone(self, **updates):
        new_path = WebPath(self._url)
        for attr in self.__slots__:
            if attr not in ('_url', '_parts', '_trailing_slash', '_cache'):
                value = getattr(self, attr)
                if hasattr(value, 'copy'):
                    value = value.copy()
                setattr(new_path, attr, value)
        
        for key, value in updates.items():
            setattr(new_path, key, value)
        
        return new_path

    def with_headers(self, **headers):
        new_headers = self._default_headers.copy()
        new_headers.update(headers)
        return self._clone(_default_headers=new_headers)
        
    def with_retries(self, retries, backoff=0.3, jitter=0.0):
        return self._clone(_retries=retries, _backoff=backoff, _jitter=jitter)
    
    def session(self, **kw):     # pragma: no skylos
        return session_cm(self, **kw)

    async def aget(self, *a, **kw):    # pragma: no skylos
        headers = self._default_headers.copy()
        if "headers" in kw:
            headers.update(kw["headers"])
            kw["headers"] = headers
        elif headers:
            kw["headers"] = headers
        
        if self._timeout is not None and "timeout" not in kw:
            kw["timeout"] = self._timeout
        
        return await aget_async(self, *a, **kw)

    def download(self, dest, **kw):
        if self._retries is not None and "retries" not in kw:
            kw["retries"] = self._retries
        
        if "backoff" not in kw:
            kw["backoff"] = self._backoff
        
        return download_file(self, dest, **kw)

    def _replace(self, **patch):
        parts = self._parts._replace(**patch)
        url = urlunsplit(parts)
        if self._trailing_slash and not url.endswith("/"):
            url += "/"
        return self._clone(_url=url, _parts=urlsplit(url))

    def __iter__(self):
        return iter(self._parts.path.strip("/").split("/")) 