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
import time
import threading
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
    __version__ = "1.0.5.3"
    __license__ = "GPL3"
    __description__ = (
        "Sends discord notifications when bt-tether connects. It also sends statistics!"
    )
    DEBOUNCE_SECONDS = 30

    COLOR_CONNECTED = 3447003  # Blue
    COLOR_DISCONNECTED = 15158332  # Re

    def on_loaded(self):
        self.discord_webhook_url = self.options.get("discord_webhook_url", "")

        # Debounce state, guarded by _debounce_lock because bt-tether may dispatch
        # events from more than one worker thread.
        self._debounce_lock = threading.Lock()
        self._last_state = None
        self._last_time = 0.0

        if self.discord_webhook_url:
            logging.info("[bt-helper-discord2] Loaded with Discord webhook configured")
        else:
            logging.warning(
                "[bt-helper-discord2] Loaded but no discord_webhook_url configured"
            )

    def _should_notify(self, state):
        """Return True if a notification for `state` should be sent right now.

        Suppresses duplicate same-state events inside DEBOUNCE_SECONDS, and only
        allows a "disconnected" notification if we previously reported "connected".
        """
        with self._debounce_lock:
            now = time.monotonic()
            if state == "disconnected" and self._last_state != "connected":
                return False
            if (
                state == self._last_state
                and (now - self._last_time) < self.DEBOUNCE_SECONDS
            ):
                return False
            self._last_state = state
            self._last_time = now
            return True

    def _send_async(self, **kwargs):
        """Fire the webhook on a daemon thread so a slow/unreachable Discord
        endpoint can't stall bt-tether's worker thread (events are dispatched
        synchronously via plugins.on())."""
        threading.Thread(target=self._notify, kwargs=kwargs, daemon=True).start()

    def on_bt_tether_connected(self, agent, event_data):
        ip = event_data.get("ip", "unknown")
        ipv6 = event_data.get("ipv6")
        device = event_data.get("device", "unknown")
        pwnagotchi_name = event_data.get("pwnagotchi_name") or pwnagotchi.name()

        if not self._should_notify("connected"):
            return

        mem = self._mem_usage()
        load = self._cpu_load()
        stat = str(self._cpu_stat())
        tempt = self._cpu_temp()
        uptim = self._uptime()
        load_avg = self._load_average()

        system_stats = (
        f"**Memory:** {mem}\n"
        f"**CPU Load:** {load}\n"
        f"**AVG Load:** {load_avg}\n"
        f"**CPU Stat:** {stat}\n"
        f"**Uptime:** {uptim}\n"
        f"**Temp:** {tempt}"
        )

        # Group connection info
        connection_info = (
            f"**IP:** `{ip}`\n"
            f"**Device:** {device}"
        )
        # Group links
        links = (
            f"[Web UI](http://{ip}:8080/)\n"
            f"[Plugins](http://{ip}:8080/plugins/)\n"
            f"[Logtail](http://{ip}:8080/plugins/logtail)\n"
            f"[Web2SSH2](http://{ip}:8083/)"
        )

        logging.info(
            f"[bt-helper-discord2] Connected: {pwnagotchi_name} - {ip} via {device}"
        )
        
        fields = [
            {"name": "Pwnagotchi", "value": pwnagotchi_name, "inline": True},
            {"name": "Connection", "value": connection_info, "inline": False},
            {"name": "Links", "value": links, "inline": False},
            {"name": "System", "value": system_stats, "inline": False},

        ]

        if ipv6:
            fields.append({"name": "IPv6", "value": f"`{ipv6}`", "inline": True})

        self._send_async(
            title="🔷 Bluetooth Tethering Connected",
            description=f"**{pwnagotchi_name}** is now connected via Bluetooth",
            color=self.COLOR_CONNECTED,
            fields=fields,
        )

    def _notify(self, title, description, color=COLOR_CONNECTED, fields=None):
        """Send a Discord embed via webhook"""
        if not URLLIB_AVAILABLE or not self.discord_webhook_url:
            return

        embed = {
            "title": title,
            "description": description,
            "color": color,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            "footer": {"text": "pwnagotchi - bt-helper-discord2 1.0.4"},
        }
        if fields:
            embed["fields"] = fields

        payload = json.dumps({"embeds": [embed]}).encode("utf-8")
        # User-Agent: DiscordBot ($url, $versionNumber)
        try:
            req = urllib.request.Request(
                self.discord_webhook_url,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "DiscordBot (https://github.com/unitMeasure/beta_plugins_pwnagotchi, 1.0.4.1)",
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

    def on_bt_tether_disconnected(self, agent, event_data):
        device = event_data.get("device", "unknown")
        reason = event_data.get("reason", "unknown")
        pwnagotchi_name = event_data.get("pwnagotchi_name") or pwnagotchi.name()

        if not self._should_notify("disconnected"):
            return

        logging.info(
            f"[bt-tether-discord] Disconnected: {pwnagotchi_name} from {device} ({reason})"
        )
        self._send_async(
            title="🔴 Bluetooth Tethering Disconnected",
            description=f"**{pwnagotchi_name}** lost its Bluetooth connection",
            color=self.COLOR_DISCONNECTED,
            fields=[
                {"name": "Pwnagotchi", "value": pwnagotchi_name, "inline": True},
                {"name": "Device", "value": device, "inline": True},
                {"name": "IP Address", "value": f"`{ip}`", "inline": True},
                {
                    "name": "Web Interface",
                    "value": f"http://{ip}:8080/",
                    "inline": False,
                },
                {"name": "Reason", "value": reason, "inline": True},
            ],
        )

    def _mem_usage(self):
        return f"{int(pwnagotchi.mem_usage() * 100)}%"

    def _cpu_load(self):
        return f"{int(pwnagotchi.cpu_load() * 100)}%"

    def _uptime(self):
        with open("/proc/uptime", "r") as f:
            uptime_seconds = float(f.readline().split()[0])
            hours = int(uptime_seconds // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            return f"{hours}h {minutes}m"

    def _cpu_stat(self):
        """
        Returns the split first line of the /proc/stat file
        """
        with open("/proc/stat", "rt") as fp:
            return list(map(int, fp.readline().split()[1:]))

    def _load_average(self):
        with open('/proc/loadavg', 'r') as f:
            parts = f.read().split()
            return f"1m: {parts[0]}, 5m: {parts[1]}, 15m: {parts[2]}"
            
    def _cpu_temp(self):

        scal = self.options.get("scale", "celsius")  # optional change

        if scal == "fahrenheit":
            temp = pwnagotchi.temperature(celsius=False)
            symbol = "F"
        elif scal == "kelvin":
            temp = pwnagotchi.temperature() + 273.15
            symbol = "K"
        else:
            temp = pwnagotchi.temperature()
            symbol = "C"  # default to celsius
        return f"{temp}{symbol}"
