from __future__ import annotations
import sys
import json
import typer
from pathlib import Path
from rich import print as rprint
from webpath.core import WebPath

app = typer.Typer(add_completion=False, help="Tiny CLI gateway for webpath")

@app.command()
def join(base: str, *segments: str):     # pragma: no skylos
    """Echo base / seg1 / seg2 ..."""
    url = WebPath(base)
    for seg in segments:
        url = url / seg
    rprint(str(url))

@app.command()
def get(
    url: str,
    pretty: bool = typer.Option(False, "--pretty", "-p"),
    retries: int = typer.Option(0, "--retries", "-r"),
    backoff: float = typer.Option(0.3, "--backoff", "-b"),
):
    r = WebPath(url).get(retries=retries, backoff=backoff)
    if pretty and "application/json" in r.headers.get("content-type", ""):
        rprint(json.dumps(r.json(), indent=2))
    else:
        sys.stdout.buffer.write(r.content)


@app.command()
def download(
    url: str,
    dest: Path = typer.Argument(..., exists=False, dir_okay=False, writable=True),
    retries: int = typer.Option(3, "--retries", "-r"),
    backoff: float = typer.Option(0.3, "--backoff", "-b"),
    checksum: str | None = typer.Option(None, "--checksum", "-c", help="Expected hex digest"),
):
    wp = WebPath(url)
    wp.download(dest, retries=retries, backoff=backoff, checksum=checksum)
    rprint(f"[green] * [/green] Saved to {dest}")

def _main_():
    app()

if __name__ == "__main__":
    _main_()
