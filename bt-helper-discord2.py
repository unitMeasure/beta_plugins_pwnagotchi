"""
Bluetooth Tether Discord Plugin

Listens to bt-tether plugin events and forwards them to Discord via webhook.

Configuration (config.toml):

    [main.plugins.bt-helper-discord2]
    enabled = true
    discord_webhook_url = "https://discord.com/api/webhooks/..."  # required
    scale = "celsius" # optional celsius (default) kelvin or fahrenheit 
"""

import logging
import json
import pwnagotchi
from pwnagotchi.plugins import Plugin

try:
    import urllib.request
    import urllib.error

    URLLIB_AVAILABLE = True
except ImportError:
    URLLIB_AVAILABLE = False
    logging.warning(
        "[bt-helper-discord2] urllib not available, Discord notifications disabled"
    )


class BTHelperDiscord2(Plugin):
    __author__ = "wsvdmeer"
    __editor__ = "avipars"
    __github__ = "https://github.com/wsvdmeer/pwnagotchi-plugins/"
    __version__ = "1.0.2"
    __license__ = "GPL3"
    __description__ = "Sends Helpful Discord notifications when bt-tether connects"

    
    def on_loaded(self):
        self.discord_webhook_url = self.options.get("discord_webhook_url", "")

        if self.discord_webhook_url:
            logging.info("[bt-helper-discord2] Loaded with Discord webhook configured")
        else:
            logging.warning(
                "[bt-helper-discord2] Loaded but no discord_webhook_url configured"
            )

    def on_bt_tether_connected(self, agent, event_data):
        ip = event_data.get("ip", "unknown")
        device = event_data.get("device", "unknown")
        pwnagotchi_name = pwnagotchi.name()

        mem = self._mem_usage()
        load = self._cpu_load()
        stat = self._cpu_stat()
        tempt = self._cpu_temp()

        logging.info(
            f"[bt-helper-discord2] Connected: {pwnagotchi_name} - {ip} via {device}"
        )
        self._notify(
            title="🔷 Bluetooth HTethering Connected",
            description=f"**{pwnagotchi_name}** is now connected on {ip}",
            color=3447003,  # Blue
            fields=[
                {"name": "Pwnagotchi", "value": pwnagotchi_name, "inline": True},
                {"name": "Device", "value": device, "inline": True},
                {"name": "Memory Usage", "value": mem, "inline": True},
                {"name": "CPU Load", "value": load, "inline": True},
                {"name": "CPU Stat", "value": stat, "inline": True},
                {"name": "Temperature", "value": tempt, "inline": True},
                {"name": "IP Address", "value": f"`{ip}`", "inline": True},
                {
                    "name": "Web Interface",
                    "value": f"http://{ip}:8080/",
                    "inline": False,
                },
                {
                    "name": "Plugins",
                    "value": f"http://{ip}:8080/plugins/",
                    "inline": False,
                },
                {
                    "name": "logtail",
                    "value": f"http://{ip}:8080/plugins/logtail",
                    "inline": False,
                },
                {
                    "name": "web2ssh2",
                    "value": f"http://{ip}:8083/",
                    "inline": False,
                },
            ],
        )

    def _notify(self, title, description, color=3447003, fields=None):
        """Send a Discord embed via webhook"""
        if not URLLIB_AVAILABLE or not self.discord_webhook_url:
            return

        import time

        embed = {
            "title": title,
            "description": description,
            "color": color,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            "footer": {"text": "pwnagotchi \u00b7 bt-helper-discord2"},
        }
        if fields:
            embed["fields"] = fields

        payload = json.dumps({"embeds": [embed]}).encode("utf-8")

        try:
            req = urllib.request.Request(
                self.discord_webhook_url,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Pwnagotchi-BT-Tether/1.0",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 204:
                    logging.info(
                        "[bt-helper-discord2] ✓ Discord notification sent successfully"
                    )
                else:
                    logging.warning(
                        f"[bt-helper-discord2] Webhook returned status {resp.status}"
                    )
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            logging.error(
                f"[bt-helper-discord2] Webhook HTTP error {e.code}: {e.reason} {error_body}"
            )
        except urllib.error.URLError as e:
            logging.error(f"[bt-helper-discord2] Webhook network error: {e.reason}")
        except Exception as e:
            logging.error(f"[bt-helper-discord2] Webhook error: {e}")

    def _mem_usage(self):
        return f"{int(pwnagotchi.mem_usage() * 100)}%"

    def _cpu_load(self):
        return f"{int(pwnagotchi.cpu_load() * 100)}%"

    def _cpu_stat(self):
        """
        Returns the split first line of the /proc/stat file
        """
        with open('/proc/stat', 'rt') as fp:
            return list(map(int,fp.readline().split()[1:]))

    def _cpu_temp(self):

        scal = self.options.get('scale', 'celsius') # optional change

        if scal == "fahrenheit":
            temp = (pwnagotchi.temperature(celsius=False))
            symbol = "F"
        elif scal == "kelvin":
            temp = pwnagotchi.temperature() + 273.15
            symbol = "K"
        else:
            # default to celsius
            temp = pwnagotchi.temperature()
            symbol = "C"
        return f"{temp}{symbol}"
