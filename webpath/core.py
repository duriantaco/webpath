from __future__ import annotations
import httpx
from urllib.parse import quote, urlencode, urlunsplit, parse_qsl, urlsplit
from urllib3.util.retry import Retry
from pathlib import Path
import hashlib
from webpath._http import _sync_http_request, _async_http_request
from webpath.cache import CacheConfig
from tqdm import tqdm

_HTTP_VERBS = ("get", "post", "put", "patch", "delete", "head", "options")

def _idna(netloc):
    try:
        return netloc.encode("idna").decode("ascii")
    except UnicodeError:
        return netloc

class _CallableBackoff(Retry):
    def __init__(self, backoff_callable, **kwargs):
        self.backoff_callable = backoff_callable
        
        kwargs.setdefault("total", 5)
        kwargs.setdefault("backoff_factor", 0)
        kwargs.setdefault("status_forcelist", None)
        
        super().__init__(**kwargs)

    def get_backoff_time(self):
        if not self.history:
            return super().get_backoff_time()
        
        last_response = self.history[-1][2]
        if last_response is None:
            return super().get_backoff_time()
        
        try:
            return self.backoff_callable(last_response)
        except Exception:
            return super().get_backoff_time()
        
class Client:
    def __init__(
        self, 
        base_url,
        *,
        headers=None,
        cache_ttl=None,
        cache_dir=None,
        retries=3,
        backoff=None,
        jitter=None,
        rate_limit=None,
        enable_logging=False,
        auto_follow=False,
        timeout=30,
    ):
        self.base_url = WebPath(base_url)
        
        retry_policy = retries
        if callable(retries) and not isinstance(retries, Retry):
            retry_policy = _CallableBackoff(backoff_callable=retries)
        
        transport = httpx.HTTPTransport(retries=(retry_policy or 0))
        async_transport = httpx.AsyncHTTPTransport(retries=(retry_policy or 0))
        
        self.sync_client = httpx.Client(
            headers=headers or {},
            timeout=timeout,
            transport=transport,
            follow_redirects=auto_follow
        )
        
        self.async_client = httpx.AsyncClient(
            headers=headers or {},
            timeout=timeout,
            transport=async_transport,
            follow_redirects=auto_follow
        )
        
        self._config = {
            "headers": headers or {},
            "cache_ttl": cache_ttl,
            "cache_dir": cache_dir,
            "retries": retry_policy,
            "backoff": backoff,
            "jitter": jitter,
            "rate_limit": rate_limit,
            "enable_logging": enable_logging,
            "auto_follow": auto_follow,
            "timeout": timeout,
            "sync_client": self.sync_client,
            "async_client": self.async_client
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
    
    async def aget(self, *segments, **params):
        return await self.path(*segments).with_query(**params).aget()
    
    async def apost(self, *segments, **kwargs):
        return await self.path(*segments).apost(**kwargs)
    
    async def aput(self, *segments, **kwargs):
        return await self.path(*segments).aput(**kwargs)
    
    async def apatch(self, *segments, **kwargs):
        return await self.path(*segments).apatch(**kwargs)
    
    async def adelete(self, *segments, **kwargs):
        return await self.path(*segments).adelete(**kwargs)
    
    def session_cm(self, **kw):
        return self.base_url.apply_config(self._config).session(**kw)
    
    def with_config(self, **updates):
        new_config = self._config.copy()
        new_config.update(updates)
        
        new_client = Client(str(self.base_url), **new_config)
        return new_client
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()
    
    def close(self):
        if self.sync_client:
            self.sync_client.close()
    
    async def aclose(self):
        if self.async_client:
            await self.async_client.aclose()

class WebPath:
    __slots__ = (
        "_url", "_parts", "_cache", "_cache_config", "_headers", "_client",
        "_trailing_slash", "_allow_auto_follow", "_enable_logging", "_rate_limit",
        "_last_request_time", "_default_headers", "_retries", "_backoff", 
        "_jitter", "_timeout", "_sync_client", "_async_client"
    )    
    
    def __init__(self, url):
        self._url = str(url)
        self._parts = urlsplit(self._url)
        self._trailing_slash = self._url.endswith("/") and not self._parts.path.endswith("/")
        self._cache = {}
        self._cache_config = None
        self._default_headers = {}
        self._retries = None
        self._backoff = 0.3
        self._last_request_time = 0
        self._headers = None
        self._client = None
        self._allow_auto_follow = None
        self._enable_logging = False
        self._rate_limit = None
        self._jitter = None
        self._timeout = None
        self._sync_client = None
        self._async_client = None

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
    def netloc(self):
        return self._parts.netloc

    @property
    def host(self):
        return _idna(self._parts.netloc.split("@")[-1].split(":")[0])

    @property
    def port(self):
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
    def parent(self):
        parts = self._parts.path.rstrip("/").split("/")
        parent_path = "/".join(parts[:-1]) or "/"
        return self._replace(path=parent_path)

    @property
    def name(self):
        path = self._parts.path.rstrip("/")
        return path.split("/")[-1]

    @property
    def suffix(self):
        dot = self.name.rfind(".")
        if dot == -1:
            return ""
        return self.name[dot:]

    def ensure_trailing_slash(self):
        if self._url.endswith("/"):
            return self
        return WebPath(self._url + "/")

    def with_query(self, **params):
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

    def without_query(self):
        return self._replace(query="")

    def with_fragment(self, tag):
        return self._replace(fragment=quote(tag))

    def apply_config(self, config):
        updates = {}
        if "headers" in config:
            updates["_default_headers"] = config["headers"]
        if "cache_ttl" in config:
            updates["_cache_config"] = CacheConfig(config["cache_ttl"], config.get("cache_dir"))
        if "sync_client" in config:
            updates["_sync_client"] = config["sync_client"]
        if "async_client" in config:
            updates["_async_client"] = config["async_client"]
        
        return self._clone(**updates)

    def __getattr__(self, item):
        if item.startswith('a') and item[1:] in _HTTP_VERBS:
            verb = item[1:]
            async def async_request_method(*args, **kwargs):
                kwargs.setdefault("retries", self._retries)
                kwargs.setdefault("timeout", self._timeout)
                kwargs["client"] = self._async_client
                
                headers = {**self._default_headers, **kwargs.get("headers", {})}
                if headers:
                    kwargs["headers"] = headers
                
                return await _async_http_request(verb, self, *args, **kwargs)
            return async_request_method
        
        if item in _HTTP_VERBS:
            def sync_request_method(*args, **kwargs):
                kwargs.setdefault("retries", self._retries)
                kwargs.setdefault("timeout", self._timeout)
                kwargs["client"] = self._sync_client
                
                headers = {**self._default_headers, **kwargs.get("headers", {})}
                if headers:
                    kwargs["headers"] = headers
                
                return _sync_http_request(item, self, *args, **kwargs)
            return sync_request_method
        
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{item}'")

    def with_cache(self, ttl=300, cache_dir=None):
        return self._clone(_cache_config=CacheConfig(ttl, cache_dir))
  
    def with_logging(self, enabled=True):
        return self._clone(_enable_logging=enabled)

    def with_rate_limit(self, requests_per_second=1.0):
        return self._clone(_rate_limit=requests_per_second, _last_request_time=0)

    def with_retries(self, retries):
        return self._clone(_retries=retries)

    def _clone(self, **updates):
        new_path = WebPath(self._url)
        for attr in self.__slots__:
            if attr not in ('_url', '_parts'):
                value = getattr(self, attr, None)
                setattr(new_path, attr, value)
        
        for key, value in updates.items():
            setattr(new_path, key, value)
        return new_path

    def with_headers(self, **headers):
        new_headers = self._default_headers.copy()
        new_headers.update(headers)
        return self._clone(_default_headers=new_headers)
    
    def session(self, **kw):
        return httpx.Client(**kw)

    def download(self, dest, **kw):
        dest = Path(dest)
        chunk_size = kw.get('chunk', 8192)
        show_progress = kw.get('progress', True)
        checksum = kw.get('checksum')
        algorithm = kw.get('algorithm', 'sha256')

        headers = self._default_headers.copy()
        headers.update(kw.get('headers', {}))
        
        bar = None
        try:
            with httpx.Client(follow_redirects=True) as client:
                with client.stream('GET', str(self), headers=headers) as response:
                    response.raise_for_status()
                    
                    total = int(response.headers.get("content-length", 0))

                    hasher = None
                    if checksum:
                        hasher = hashlib.new(algorithm)
                    
                    if show_progress and total > 0:
                        try:
                            bar = tqdm(total=total, unit="B", unit_scale=True, leave=False, desc=dest.name)
                        except ImportError:
                            pass
                    
                    with dest.open("wb") as f:
                        for chunk in response.iter_bytes(chunk_size):
                            f.write(chunk)
                            if hasher:
                                hasher.update(chunk)
                            if bar:
                                bar.update(len(chunk))
        
        except Exception:
            if dest.exists():
                dest.unlink(missing_ok=True)
            raise
        finally:
            if bar:
                bar.close()
        if checksum and hasher:
            if hasher.hexdigest() != checksum.lower():
                dest.unlink(missing_ok=True)
                raise ValueError(f"Checksum mismatch: expected {checksum}, got {hasher.hexdigest()}")
            
        return dest

    def _replace(self, **patch):
        parts = self._parts._replace(**patch)
        url = urlunsplit(parts)
        if self._trailing_slash and not url.endswith("/"):
            url += "/"
        return self._clone(_url=url, _parts=urlsplit(url))

    def __iter__(self):
        return iter(self._parts.path.strip("/").split("/"))