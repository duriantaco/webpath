from __future__ import annotations
import sys
import json
import typer
from rich import print as rprint
from webpath.core import WebPath

app = typer.Typer(add_completion=False, help="Tiny CLI gateway for webpath")

@app.command()
def join(base, *segments):     # pragma: no skylos
    url = WebPath(base)
    for seg in segments:
        url = url / seg
    rprint(str(url))

@app.command()
def get(
    url,
    pretty = typer.Option(False, "--pretty", "-p"),
    retries = typer.Option(0, "--retries", "-r"),
    backoff = typer.Option(0.3, "--backoff", "-b"),
):
    r = WebPath(url).get(retries=retries, backoff=backoff)
    if pretty and "application/json" in r.headers.get("content-type", ""):
        rprint(json.dumps(r.json(), indent=2))
    else:
        sys.stdout.buffer.write(r.content)


@app.command()
def download(
    url,
    dest = typer.Argument(..., exists=False, dir_okay=False, writable=True),
    retries= typer.Option(3, "--retries", "-r"),
    backoff = typer.Option(0.3, "--backoff", "-b"),
    checksum= typer.Option(None, "--checksum", "-c", help="Expected hex digest"),
):
    wp = WebPath(url)
    wp.download(dest, retries=retries, backoff=backoff, checksum=checksum)
    rprint(f"[green] * [/green] Saved to {dest}")

def _main_():
    app()

if __name__ == "__main__":
    _main_()
