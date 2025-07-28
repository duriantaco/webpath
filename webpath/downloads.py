from __future__ import annotations
import hashlib
from pathlib import Path
from tqdm import tqdm
from webpath._http import http_request

def download_file(
    url,
    dest,
    *,
    chunk = 8192,
    progress= True,
    retries = 3,
    backoff = 0.3,
    checksum = None,
    algorithm = "sha256",
    **req_kw,
):
    dest = Path(dest)
    bar = None
    
    try:
        r = http_request("get", url, stream=True, retries=retries, backoff=backoff, **req_kw)
        r.raise_for_status()

        total = int(r.headers.get("content-length", 0))
        hasher = hashlib.new(algorithm) if checksum else None

        if progress:
            try:
                bar = tqdm(total=total, unit="B", unit_scale=True, leave=False)
            except ImportError:
                pass

        with dest.open("wb") as fh:
            for block in r.iter_content(chunk):
                if block:
                    fh.write(block)
                    if hasher:
                        hasher.update(block)
                    if bar:
                        bar.update(len(block))
                        
    except Exception:
        if dest.exists():
            dest.unlink(missing_ok=True)
        raise
    finally:
        if bar:
            bar.close()

    if checksum and hasher and hasher.hexdigest() != checksum.lower():
        dest.unlink(missing_ok=True)
        raise ValueError(
            f"Checksum mismatch for {dest.name}: "
            f"expected {checksum}, got {hasher.hexdigest()}"
        )
    return dest