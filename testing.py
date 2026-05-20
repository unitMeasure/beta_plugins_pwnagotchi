import logging
import pwnagotchi.plugins as plugins
import os
import subprocess
import shutil
from flask import abort, send_from_directory, render_template_string, request, make_response


class testing(plugins.Plugin):
    __GitHub__ = "https://github.com/unitMeasure/pwn-plugins/"
    __author__ = "avipars"
    __editor__ = "avipars"
    __version__ = "0.0.1"
    __license__ = "GPL3"
    __description__ = "Testing out stuff"
    __name__ = "testing"
    
    def __init__(self):
            self.log = logging.getLogger(__name__)
            self.ready = False

    def on_loaded(self):
        logging.info("[testing] plugin loaded")

    def on_webhook(self, path, request):
            # Only handle our own plugin path: /plugins/reaverdiag/ (or any subpath)
            if not path or path == "/":
                return  # let other plugins handle the root, we ignore it

            # Strip leading slash for matching
            if path.lstrip("/") == "testing":
                # Gather all info fresh on each request
                info = self._gather_info()

                # Build HTML page using the user’s existing theme style
                html_head = (
                    '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">'
                    '<meta name="csrf_token" content="{{ csrf_token() }}">'
                    '<link href="https://fonts.cdnfonts.com/css/white-rabbit-2" rel="stylesheet">'
                    '<title>#title#</title>'
                    '<style>body{height:100%;background-color:#333;color:#fff;direction:ltr;'
                    'font-family:"White Rabbit","Courier New",Courier,monospace;font-size:2em;'
                    'font-variant-numeric:slashed-zero;text-align:center;text-shadow:0 1px 3px rgba(0,0,0,.5);'
                    'unicode-bidi:bidi-override}h1,h3{color:#0C0;padding-bottom:10px;'
                    'text-shadow:-1px-1px 0 rgba(0,0,0,.3)}a{color:#0C0;text-decoration:none}'
                    'a:hover{font-weight:bold;text-decoration:underline}table{width:50%;'
                    'border-collapse:collapse;margin:20px auto}table th,table td{'
                    'border:1px solid#1e1e1e;padding:1rem;text-align:left;font-size:1.5rem}'
                    'table thead{background-color:#1e1e1e}.note{font-size:1em;margin-top:20px;'
                    'line-height:1.5em}small{font-size:1.2rem;margin-bottom:1rem;display:block;'
                    'line-height:1.5rem}@media(max-width:1199.98px){table{width:80%}'
                    'table th,table td{font-size:2.5rem}}</style></head><body>'
                )
                html_foot = (
                    '<div class="note"><p><a href="https://pwncrack.org" target="_blank">'
                    'pwncrack.org</a><br />key: N/A</p>'
                    '<p><a href="https://pwncrack.org/nets.html" target="_blank">Your Nets</a> | '
                    '<a href="https://pwncrack.org/leaderboard.html" target="_blank">Leaderboard</a> | '
                    '<a href="https://pwncrack.org/stats.html" target="_blank">Global Stats</a></p>'
                    '</div></body></html>'
                )

                html_page = html_head.replace('#title#', 'pwncrack | Reaver Diag')
                html_page += '<h1>🛰️ System Diagnostics</h1>'
                html_page += '<table><thead><tr><th>Item</th><th>Value</th></tr></thead><tbody>'

                for key, val in info.items():
                    # Escape any HTML-sensitive characters
                    safe_val = str(val).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    # Replace newlines for display
                    safe_val = safe_val.replace("\n", "<br>")
                    html_page += f'<tr><td>{key}</td><td>{safe_val}</td></tr>'

                html_page += '</tbody></table>'
                html_page += html_foot
                return render_template_string(html_page), 200
            else:
                return f"path issue {path.lstrip("/")}"
                # If path is not ours, let Pwnagotchi’s web framework handle it (or 404)

    def _gather_info(self):
        """Runs all diagnostics and returns a dict; also logs everything."""
        info = {}

        # 1. whoami
        try:
            who = subprocess.check_output(["whoami"], text=True, timeout=5).strip()
            info["whoami"] = who
        except Exception as e:
            info["whoami"] = f"Error: {e}"

        # 2. Current PATH (before extension)
        original_path = os.environ.get("PATH", "")
        info["Original PATH"] = original_path

        # 3. Temporarily extend PATH to include common reaver locations
        extra_dirs = "/usr/sbin:/sbin:/usr/bin"
        current_path = os.environ.get("PATH", "")
        extended_path = current_path + (":" if current_path else "") + extra_dirs
        os.environ["PATH"] = extended_path
        info["Extended PATH"] = extended_path

        # 4. Locate reaver with original and extended PATH
        os.environ["PATH"] = original_path  # back to original to test
        reaver_original = shutil.which("reaver")
        info["Reaver (original PATH)"] = reaver_original if reaver_original else "NOT FOUND"

        os.environ["PATH"] = extended_path
        reaver_extended = shutil.which("reaver")
        info["Reaver (extended PATH)"] = reaver_extended if reaver_extended else "NOT FOUND"

        # 5. Try to actually run reaver (if found)
        if reaver_extended:
            try:
                result = subprocess.check_output(
                    [reaver_extended, "--help"],
                    text=True, stderr=subprocess.STDOUT, timeout=10
                )
                info["Reaver --help (first lines)"] = "\n".join(result.splitlines()[:10])
            except subprocess.CalledProcessError as e:
                info["Reaver run"] = f"Exit code {e.returncode}: {e.output[:300]}"
            except Exception as e:
                info["Reaver run"] = f"Error: {e}"
        else:
            info["Reaver run"] = "Not attempted (binary not found)"

        # Restore original PATH
        os.environ["PATH"] = original_path

        # --- Log all gathered data to Pwnagotchi log ---
        self.log.info("=== Reaver Diagnostics ===")
        for key, val in info.items():
            self.log.info(f"{key}: {val}")

        return info
