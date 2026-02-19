#!/usr/bin/env python3
"""
Simple HTTP server for PHATE Gallery.
"""

import http.server
import socketserver
import os

PORT = 8000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
HTML_FILE = 'wandb_multiselect_gallery_old.html'

class GalleryHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom request handler that serves the gallery HTML."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        """Handle GET requests."""
        # Serve main HTML file at root
        if self.path == '/' or self.path == '':
            self.path = '/' + HTML_FILE
        return super().do_GET()

    def log_message(self, format, *args):
        """Log to console."""
        print(f"[{self.log_date_time_string()}] {format % args}")

def run_server():
    """Start the HTTP server."""
    os.chdir(DIRECTORY)

    with socketserver.TCPServer(("", PORT), GalleryHTTPRequestHandler) as httpd:
        print(f"\n{'='*60}")
        print(f" PHATE Gallery Server")
        print(f"{'='*60}")
        print(f" Serving directory: {DIRECTORY}")
        print(f" Main HTML: {HTML_FILE}")
        print(f" URL: http://localhost:{PORT}/")
        print(f"{'='*60}")
        print(f" Press Ctrl+C to stop...\n")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")

if __name__ == "__main__":
    run_server()
