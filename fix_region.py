import os
import pwnagotchi
from pwnagotchi import restart
import pwnagotchi.plugins as plugins
import logging
import _thread
import subprocess
import re

NETFIX_SERV = """
[Unit]
Description=Custom iw Domain Set Script
After=default.target

[Service]
ExecStart=/root/network-fix.sh &

[Install]
WantedBy=default.target
"""

NETFIX_SH = """
#!/bin/bash
iw reg set """

SERV_PATH = '/etc/systemd/system/network-fix.service'
SH_PATH = '/root/network-fix.sh'

class fix_region(plugins.Plugin):
    __name__ = 'Fix_Region'
    __author__ = '@V0rT3x https://github.com/V0r-T3x'
    __editor__ = 'avipars'
    __version__ = '1.0.0.2'
    __license__ = 'GPL3'
    __description__ = 'Let you change the iw region to unlock channel'
    __defaults__ = {
        "enabled": False,
        "region": "US",
    }

    def __init__(self):
        self.ready = False
        self.mode = 'MANU'
        # Helper to get config safely
        self.target_region = "US"
        if 'main' in pwnagotchi.config and 'plugins' in pwnagotchi.config['main']:
             if 'fix_region' in pwnagotchi.config['main']['plugins']:
                 self.target_region = pwnagotchi.config['main']['plugins']['fix_region']['region']
        
        logging.info(f'[FIX_REGION] Target Region: {self.target_region}')

    def on_loaded(self):
        logging.info('[FIX_REGION] plugin loaded')

        if not os.path.exists(SH_PATH):
            with open(SH_PATH, "w") as file:
                file.write(NETFIX_SH + self.target_region)
            os.system('chmod +x '+SH_PATH)

        if not os.path.exists(SERV_PATH):
            with open(SERV_PATH, "w") as file:
                file.write(NETFIX_SERV)
            
            os.system(f'sudo iw reg set {self.target_region}')
            os.system('sudo systemctl enable network-fix')
            os.system('sudo systemctl start network-fix')
            try:
                _thread.start_new_thread(restart, (self.mode,))
            except Exception as ex:
                logging.error(ex)

    def on_unload(self, ui):
        logging.info('[FIX_REGION] plugin unloaded')        

        if os.path.exists(SERV_PATH):
            os.system('rm '+SERV_PATH)
        if os.path.exists(SH_PATH):
            os.system('rm '+SH_PATH)
            
        os.system('sudo systemctl stop network-fix')
        os.system('sudo systemctl disable network-fix')

    def on_webhook(self, path, request):
        # 1. Get Regulatory Details
        try:
            reg_output = subprocess.check_output(['iw', 'reg', 'get']).decode('utf-8')
        except Exception as e:
            reg_output = f"Error getting reg info: {str(e)}"

        # 2. Get Available Channels
        try:
            # We use wlan0 because mon0 might not show the hardware limitations correctly
            chan_output = subprocess.check_output(['iwlist', 'wlan0', 'channel']).decode('utf-8')
            
            # Simple regex to extract just the channel numbers
            channels = re.findall(r'Channel (\d+)', chan_output)
            channel_list_str = ", ".join(channels)
            channel_count = len(channels)
        except Exception as e:
            channel_list_str = "Error reading channels"
            channel_count = 0
            chan_output = str(e)

        # 3. Build the HTML
        html = f"""
        <html>
        <head>
            <title>Fix_Region Info</title>
            <style>
                body {{ font-family: monospace; padding: 20px; background: #333; color: #fff; }}
                .box {{ background: #444; padding: 15px; margin-bottom: 20px; border-radius: 5px; }}
                h2 {{ border-bottom: 1px solid #777; padding-bottom: 5px; }}
                pre {{ background: #222; padding: 10px; overflow-x: auto; }}
                .highlight {{ color: #00ff00; font-weight: bold; }}
            </style>
        </head>
        <body>
            <h1>Fix_Region Status</h1>
            
            <div class="box">
                <h2>Configuration</h2>
                <p>Target Region (Config): <span class="highlight">{self.target_region}</span></p>
                <p>Active Channels ({channel_count}): <span class="highlight">{channel_list_str}</span></p>
            </div>

            <div class="box">
                <h2>Regulatory Domain (iw reg get)</h2>
                <pre>{reg_output}</pre>
            </div>

            <div class="box">
                <h2>Raw Channel Output</h2>
                <pre>{chan_output}</pre>
            </div>
        </body>
        </html>
        """
        return html
