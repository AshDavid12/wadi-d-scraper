#!/usr/bin/env python3
"""Serve the demo competitor site on http://127.0.0.1:8765 (set DEMO_VERSION=1 or 2)."""

from __future__ import annotations

import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from demo_site import BASE, demo_fetch, demo_page_urls, index_html, page_html

PORT = 8765
VERSION = int(os.environ.get("DEMO_VERSION", "1"))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        url = f"http://127.0.0.1:{PORT}{self.path}"
        parsed = urlparse(self.path)

        if parsed.path.endswith((".xml", ".txt")) or parsed.path == "/robots.txt":
            code, body, ct = demo_fetch(url, VERSION)
            if code != 200:
                self.send_error(code)
                return
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path in ("", "/"):
            body = index_html(VERSION)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode())
            return

        if parsed.path.startswith(("/pages/", "/collections/", "/blogs/")):
            html = page_html(url, VERSION)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode())
            return

        self.send_error(404)

    def log_message(self, fmt: str, *args) -> None:
        msg = fmt % args
        # Browsers / DevTools often probe https://127.0.0.1:PORT on an HTTP-only server.
        if "Bad request version" in msg or "Bad HTTP/0.9 request type" in msg:
            return
        if '"GET /json/version HTTP/' in msg:
            return
        print(msg)


def main() -> None:
    home = f"http://127.0.0.1:{PORT}/"
    print(f"Demo site v{VERSION} — open in browser: {home}")
    for path in demo_page_urls(VERSION):
        print(f"  {path}")
    print(f"  {BASE}/sitemap.xml")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
