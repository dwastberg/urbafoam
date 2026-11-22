"""Loopback-only preview server. npm provides the prebuilt vtk.js browser bundle."""

import json
import mimetypes
import shutil
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

import click

from .case import MeshExport, PreviewError, setup_scene


def serve(case, open_browser):
    ui = Path(__file__).parent
    vtk = ui / "node_modules/vtk.js/vtk.js"
    if not vtk.is_file():
        raise click.ClickException(f'Install the optional viewer with npm --prefix "{ui}" ci')
    try:
        scene, models = setup_scene(case)
    except PreviewError as exc:
        raise click.ClickException(str(exc)) from exc

    files = {"/": ui / "index.html", "/vtk.js": vtk, "/viewer.js": ui / "viewer.js", "/style.css": ui / "style.css"}
    files.update({layer["url"]: path for layer, path in zip(scene["models"], models)})

    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, mime, length):
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

        def send_json(self, data, status=200):
            body = json.dumps(data).encode()
            self.reply(status, "application/json", len(body))
            self.wfile.write(body)

        def do_GET(self):
            if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
                self.send_error(403)
                return
            path = urlsplit(self.path).path
            try:
                if path == "/api/setup":
                    self.send_json(scene)
                elif path == "/api/mesh":
                    self.send_json(export.layers_for_run())
                elif file := files.get(path) or export.files.get(path):
                    with file.open("rb") as stream:
                        self.reply(200, mimetypes.guess_type(file)[0] or "application/octet-stream",
                                   file.stat().st_size)
                        shutil.copyfileobj(stream, self.wfile)
                else:
                    self.send_error(404)
            except (PreviewError, FileNotFoundError) as exc:
                self.send_json({"error": str(exc)}, 409)
            except (BrokenPipeError, ConnectionResetError):
                pass

    with TemporaryDirectory(prefix="urbafoam-preview-") as temp:
        export = MeshExport(case, temp)
        with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            url = f"http://127.0.0.1:{server.server_port}/"
            click.echo(f"Previewing {case}\n{url}\nPress Ctrl+C to close.")
            if open_browser:
                webbrowser.open(url)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
