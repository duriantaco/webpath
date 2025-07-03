from __future__ import annotations

import hashlib
import importlib
import os
from pathlib import Path
from typing import Optional

from webpath._http import http_request

def download_file(
    url,
    dest: str | os.PathLike,
    *,
    chunk: int = 8192,
    progress: bool = True,
    retries: int = 3,
    backoff: float = 0.3,
    checksum: Optional[str] = None,
    algorithm: str = "sha256",
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
                mod = importlib.import_module("tqdm")
                if hasattr(mod, "tqdm"):
                    bar = mod.tqdm(total=total, unit="B", unit_scale=True, leave=False)
            except ModuleNotFoundError:
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