import os
import html
import shutil
import logging
import subprocess
import shutil

import pwnagotchi.plugins as plugins


class diagnostics(plugins.Plugin):
    __name__ = 'Diagnostics'
    __author__ = 'avipars'
    __version__ = '1.0.0.1'
    __license__ = 'GPL3'
    __description__ = 'Diagnostic utility page for checking binaries, PATH and environment'

    def __init__(self):
        logging.info('[DIAGNOSTICS] plugin created')

    def on_loaded(self):
        logging.info('[DIAGNOSTICS] plugin loaded')

    def on_unload(self, ui):
        logging.info('[DIAGNOSTICS] plugin unloaded')

    def _run_shell(self, command):
        try:
            result = subprocess.check_output(
                command,
                shell=True,
                stderr=subprocess.STDOUT,
                timeout=10
            ).decode('utf-8', errors='ignore')

            return {
                "success": True,
                "output": result.strip()
            }

        except subprocess.CalledProcessError as e:
            return {
                "success": False,
                "output": e.output.decode('utf-8', errors='ignore').strip()
            }

        except Exception as e:
            return {
                "success": False,
                "output": str(e)
            }

    def _binary_status(self, binary):
        path = shutil.which(binary)

        if path:
            return f'<span class="highlight">FOUND</span> ({html.escape(path)})'

        return '<span class="bad">NOT FOUND</span>'

    def _check_tool(self, name: str) -> bool:
        res = None
        try:
            subprocess.run([name, '--version'], capture_output=True, timeout=5)
            res = f'found tool {name}'
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            res = None

        if path:
            return f'<span class="highlight">FOUND</span> ({html.escape(path)})'

        return '<span class="bad">NOT FOUND</span>'

    # ------------------------------------------------------------------
    # Helper: check if external tool exists
    # ------------------------------------------------------------------
    def _check_tool(self, name: str) -> bool:
        """
        Better tool detection.

        Some tools:
        - return non-zero on --help
        - return non-zero on --version
        - require arguments and still print valid output
        - print usage to stderr

        So we:
        1. verify binary exists in PATH
        2. try several common flags
        3. treat meaningful output as success
        """

        # First: make sure binary exists
        binary_path = shutil.which(name)

        if not binary_path:
            return False

        cmds = [
            [name, '--version'],
            [name, '-V'],
            [name, '-v'],
            [name, '--help'],
            [name, '-h']
        ]

        success_keywords = [
            "usage",
            "help",
            "version",
            "v1.",
            "v2.",
            "v3.",
            "options",
            "syntax",
            "mdk4",
            "reaver",
            "bully",
            "hcxdumptool",
            "aircrack",
            "aireplay"
        ]

        for cmd in cmds:
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                output = (
                    (result.stdout or "") +
                    (result.stderr or "")
                ).strip().lower()

                # Many security tools return non-zero
                # even when working properly.
                # So check for meaningful output instead.
                if output:
                    for keyword in success_keywords:
                        if keyword in output:
                            return True

            except subprocess.TimeoutExpired:
                continue

            except FileNotFoundError:
                return False

            except Exception:
                continue

        return False

    def _test_binary(self, name):
        cmds = [
            f"{name} --version",
            f"{name} -v",
            f"{name} -h",
            f"{name} --help"
        ]

        results = []

        for cmd in cmds:
            result = self._run_shell(cmd)

            if result["output"]:
                results.append({
                    "cmd": cmd,
                    "success": result["success"],
                    "output": result["output"]
                })

        return results

    def _build_command_blocks(self, title, results):
        blocks = ""

        if not results:
            return f"""
            <div class="box">
                <h2>{title}</h2>
                <pre>No output returned</pre>
            </div>
            """

        for result in results:
            status = "SUCCESS" if result["success"] else "ERROR"

            blocks += f"""
            <div class="box">
                <h2>{html.escape(result['cmd'])}</h2>

                <p>
                    Status:
                    <span class="{'highlight' if result['success'] else 'bad'}">
                        {status}
                    </span>
                </p>

                <pre>{html.escape(result['output'])}</pre>
            </div>
            """

        return blocks

    def on_webhook(self, path, request):
        logging.info('[DIAGNOSTICS] webhook opened')

        whoami = self._run_shell('whoami')
        env_path = os.environ.get('PATH', '')

        reaver_results = self._test_binary('reaver')
        bully_results = self._test_binary('bully')
        mdk4_results = self._test_binary('mdk4')
        hcxdumptool_results = self._test_binary('hcxdumptool')
        aireplay_results = self._test_binary('aireplay-ng')

        html_page = f"""
        <html>
        <head>
            <title>Pwnagotchi Diagnostics</title>

            <style>
                body {{
                    font-family: monospace;
                    padding: 20px;
                    background: #333;
                    color: #fff;
                }}

                .box {{
                    background: #444;
                    padding: 15px;
                    margin-bottom: 20px;
                    border-radius: 5px;
                }}

                h1 {{
                    color: #00ff99;
                }}

                h2 {{
                    border-bottom: 1px solid #777;
                    padding-bottom: 5px;
                }}

                pre {{
                    background: #222;
                    padding: 10px;
                    overflow-x: auto;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                }}

                .highlight {{
                    color: #00ff00;
                    font-weight: bold;
                }}

                .bad {{
                    color: #ff5555;
                    font-weight: bold;
                }}

                table {{
                    width: 100%;
                    border-collapse: collapse;
                }}

                td {{
                    padding: 8px;
                    border-bottom: 1px solid #666;
                    vertical-align: top;
                }}
            </style>
        </head>

        <body>
            <h1>Pwnagotchi Diagnostics</h1>

            <div class="box">
                <h2>Environment</h2>

                <table>
                    <tr>
                        <td>Current User</td>
                        <td>{html.escape(whoami['output'])}</td>
                    </tr>

                    <tr>
                        <td>PATH</td>
                        <td>{html.escape(env_path)}</td>
                    </tr>
                </table>
            </div>

            <div class="box">
                <h2>Binary Checks</h2>

                <table>
                    <tr>
                        <td>reaver</td>
                        <td>{self._binary_status('reaver')}</td>
                    </tr>

                    <tr>
                        <td>bully</td>
                        <td>{self._binary_status('bully')}</td>
                    </tr>

                    <tr>
                        <td>mdk4</td>
                        <td>{self._binary_status('mdk4')}</td>
                    </tr>

                    <tr>
                        <td>aireplay-ng</td>
                        <td>{self._binary_status('aireplay-ng')}</td>
                    </tr>

                    <tr>
                        <td>hcxdumptool</td>
                        <td>{self._binary_status('hcxdumptool')}</td>
                    </tr>
                </table>
            </div>

            {self._build_command_blocks("Reaver Tests", reaver_results)}

            {self._build_command_blocks("Bully Tests", bully_results)}

            {self._build_command_blocks("MDK4 Tests", mdk4_results)}

            {self._build_command_blocks("aireplay-ng Tests", aireplay_results)}

            {self._build_command_blocks("hcxdumptool Tests", hcxdumptool_results)}

        </body>
        </html>
        """

        return html_page
