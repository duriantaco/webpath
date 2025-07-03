
import threading
from webpath.core import _idna

def test_idna_cache_thread_safety():
    domains = [f"test{i}.bücher.de" for i in range(100)]
    results = {}
    errors = []
    
    def worker(domain):
        try:
            result = _idna(domain)
            results[domain] = result
        except Exception as e:
            errors.append(e)
    
    threads = []
    for domain in domains:
        t = threading.Thread(target=worker, args=(domain,))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    assert len(errors) == 0
    assert len(results) == 100
    for domain, result in results.items():
        assert result.startswith("test") and "xn--" in result

def test_idna_cache_size_limit():
    from webpath.core import _IDNA_CACHE, _IDNA_CACHE_MAX_SIZE
    
    _IDNA_CACHE.clear()
    
    for i in range(_IDNA_CACHE_MAX_SIZE + 100):
        _idna(f"domain{i}.example.com")
    
    assert len(_IDNA_CACHE) <= _IDNA_CACHE_MAX_SIZE