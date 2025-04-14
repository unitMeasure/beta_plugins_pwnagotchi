import os
import logging
from http.server import SimpleHTTPRequestHandler, HTTPServer
import pwnagotchi

import pwnagotchi.plugins as plugins
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts


class MyHTTPRequestHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        # Serve files from 
        base_path = "/home/pi/handshakes"
        # Get the original path
        path = super().translate_path(path)
        # Replace the server root with our base path
        relpath = os.path.relpath(path, os.getcwd())
        fullpath = os.path.join(base_path, relpath)
        return fullpath

    def log_message(self, format, *args):
        logging.info(f"[HttpServerPlugin] {self.client_address[0]} - {format % args}")

class HttpServerPlugin(plugins.Plugin):
    __author__ = 'Hades, edited by @avipars'
    __version__ = '1.0.0.4'
    __license__ = 'GPL3'
    __description__ = 'HTTP Server Plugin'
    __github__ = 'https://github.com/itsdarklikehell/pwnagotchi-plugins/blob/master/httpserver.py'
    __defaults__ = {
        "enabled": False,
    }

    def on_loaded(self):
        logging.info("[HttpServerPlugin] Loaded")
        self.start_http_server()

    def on_unload(self, ui):
        logging.info("[HttpServerPlugin] Unloaded")
        self.stop_http_server()

    def start_http_server(self):
        try:
            server_address = ('', 8000)
            self.httpd = HTTPServer(server_address, MyHTTPRequestHandler)
            logging.info("[HttpServerPlugin] Starting HTTP server on port 8000")
            self.httpd.serve_forever()

        except Exception as e:
            logging.error(f"[HttpServerPlugin] Error starting HTTP server: {e}")

    def stop_http_server(self):
        try:
            if hasattr(self, 'httpd'):
                logging.error("[HttpServerPlugin] Shutting Down HTTP Server.")
                self.httpd.shutdown()

        except Exception as e:
            logging.error(f"[HttpServerPlugin] Error stopping HTTP server: {e}")

# Instantiate the plugin
http_server_plugin = HttpServerPlugin()