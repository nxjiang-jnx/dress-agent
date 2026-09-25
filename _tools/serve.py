#!/usr/bin/env python3
"""Serve the site like `python -m http.server`, but make browsers revalidate every file.

Plain http.server sends no Cache-Control, so a browser may keep showing an old index.html for
hours after an edit. This asks it to check each time (unchanged files still come back as 304),
and stays quiet when a browser drops a video request halfway, which is normal.

    python _tools/serve.py 8000          # from dress-agent/, then open http://localhost:8000/
"""
import functools
import http.server
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def copyfile(self, source, outputfile):
        try:
            super().copyfile(source, outputfile)
        except (BrokenPipeError, ConnectionResetError):
            pass   # the browser stopped reading (a video seek or a new source)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    handler = functools.partial(Handler, directory=str(SITE))
    with http.server.ThreadingHTTPServer(("", port), handler) as httpd:
        print(f"Serving {SITE} on http://localhost:{port}/")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
