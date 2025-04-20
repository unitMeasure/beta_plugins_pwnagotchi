import os
from flask import make_response, send_file, render_template_string
from pwnagotchi import plugins

class HandshakeViewer(plugins.Plugin):
    __author__ = 'avipars'
    __version__ = '0.0.2'
    __license__ = 'GPL3'
    __description__ = 'Simple viewer and downloader for captured handshakes via webhook.'
    __github__ = 'https://github.com/avipars'
    __defaults__ = {
        "enabled": False
    }
    def __init__(self):

        self.handshake_dir = "/home/pi/handshakes/"

    def on_loaded(self):
        if not os.path.exists(self.handshake_dir):
            os.makedirs(self.handshake_dir)
        self.ready = True

    def on_webhook(self, path, request):
        """
        Serves a simple HTML list of handshake files and allows downloads.
        """
        subpath = path.strip('/')
        if subpath.startswith('download/'):
            filename = subpath.replace('download/', '', 1)
            file_path = os.path.join(self.handshake_dir, filename)
            if os.path.isfile(file_path):
                return send_file(file_path, as_attachment=True)
            else:
                return make_response(f"File '{filename}' not found.", 404)

        # Default route: list files
        try:
            files = [f for f in os.listdir(self.handshake_dir) if f.endswith('.pcap')]
        except FileNotFoundError:
            files = []

        html_template = """
        <html>
            <head><title>Handshake Viewer</title></head>
            <body>
                <h2>Available Handshakes</h2>
                <ul>
                {% for file in files %}
                    <li>
                        {{ file }} -
                        <a href="/plugins/handshake_viewer/download/{{ file }}">Download</a>
                    </li>
                {% endfor %}
                </ul>
            </body>
        </html>
        """
        return render_template_string(html_template, files=files)
