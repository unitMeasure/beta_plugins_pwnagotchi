import threading
import time
import subprocess
import logging
import re

import pwnagotchi.plugins as plugins

class UsbWifiWatch(plugins.Plugin):
    __author__ = "unitMeasure"
    __version__ = "0.0.1"
    __license__ = "GPL3"
    __description__ = "Show USB devices and wlan interface modes on screen"
    __name__ = "UsbWifiWatch"

    def __init__(self):
        self.running = False
        self.thread = None
        self.poll_interval = 5  # seconds
        self.last_usb_report = ""    # human readable
        self.last_wifi_report = ""   # human readable
        self.base_usb_ids = set()    # optionally populate with base system ids to ignore
        self.lock = threading.Lock()

    def on_loaded(self):
        logging.info("[usb_wifi_watch] plugin loaded")
        # If you know some base USB IDs to ignore, add them here, for example:
        # self.base_usb_ids = {"1d6b:0002", "1d6b:0003"}  # kernel root hubs etc

    def on_config_changed(self, config):
        self.config = config
        # allow user override of poll interval via config if desired
        try:
            v = int(self.config.get("plugins", {}).get("usb_wifi_watch", {}).get("poll_interval", self.poll_interval))
            self.poll_interval = max(1, v)
        except Exception:
            pass

    def start_worker(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self.worker, daemon=True)
        self.thread.start()

    def stop_worker(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
            self.thread = None

    # Worker thread - polls lsusb and iwconfig
    def worker(self):
        while self.running:
            try:
                usb_report = self.check_lsusb()
                wifi_report = self.check_iwconfig()
                with self.lock:
                    self.last_usb_report = usb_report
                    self.last_wifi_report = wifi_report
            except Exception as e:
                logging.exception("[usb_wifi_watch] worker error: %s", e)
            time.sleep(self.poll_interval)

    # parse lsusb output and return a human friendly string of devices excluding base ids
    def check_lsusb(self):
        try:
            p = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=2)
            out = p.stdout.strip().splitlines()
        except Exception as e:
            logging.debug("[usb_wifi_watch] lsusb failed: %s", e)
            return "lsusb not available"

        devices = []
        for line in out:
            # example line: Bus 002 Device 003: ID 046d:c52b Logitech, Inc. Unifying Receiver
            m = re.search(r"ID\s+([0-9a-fA-F]{4}:[0-9a-fA-F]{4})\s+(.*)$", line)
            if m:
                vidpid = m.group(1).lower()
                desc = m.group(2).strip()
            else:
                # fallback, keep full line
                vidpid = None
                desc = line.strip()
            if vidpid and vidpid in self.base_usb_ids:
                continue
            devices.append((vidpid, desc))

        if not devices:
            return "No external USB devices detected"
        # format a short list
        short = []
        for vidpid, desc in devices:
            if vidpid:
                short.append(f"{vidpid} {desc}")
            else:
                short.append(desc)
        return "; ".join(short)

    # parse iwconfig output for wlan0 and wlan0mon
    def check_iwconfig(self):
        try:
            p = subprocess.run(["iwconfig"], capture_output=True, text=True, timeout=2)
            out = p.stdout
        except Exception as e:
            logging.debug("[usb_wifi_watch] iwconfig failed: %s", e)
            return "iwconfig not available"

        # iwconfig prints sections per interface, we search for wlan0 and wlan0mon paragraphs
        # A simple parse: split by two newlines and search headings
        sections = re.split(r"\n{1,2}", out)
        reports = []
        for section in sections:
            # find interface name at start like "wlan0     IEEE 802.11  ESSID:..."
            m = re.match(r"^\s*([^\s:]+)\s+", section)
            if not m:
                continue
            ifname = m.group(1)
            if ifname not in ("wlan0", "wlan0mon"):
                continue

            # detect mode: look for "Mode:Managed" or "Mode:Monitor" or "Mode:Managed" with spaces
            mode = None
            mm = re.search(r"Mode[:=]\s*([A-Za-z]+)", section, re.IGNORECASE)
            if mm:
                mode = mm.group(1).lower()
            else:
                # fallback check common words
                if "monitor" in section.lower():
                    mode = "monitor"
                elif "managed" in section.lower():
                    mode = "managed"

            # detect presence
            if mode:
                reports.append(f"{ifname}: {mode}")
            else:
                reports.append(f"{ifname}: unknown")

        if not reports:
            return "No wlan0 or wlan0mon"
        return "; ".join(reports)

    # Update UI - this should be called by the framework regularly
    def on_ui_update(self, ui):
        # start worker if not running
        if not self.running:
            self.start_worker()

        # read latest reports
        with self.lock:
            usb = self.last_usb_report
            wifi = self.last_wifi_report

        # The following attempts to draw text on the UI. If your UI uses different API adapt here.
        # Keep it small and unobtrusive. If ui.draw.text is not available, fallback to ui.show or logs.
        try:
            # many Pwnagotchi UIs expose a draw object with text method
            # position values may need adjusting for your face size
            display_lines = []
            display_lines.append("USB: " + (usb or "scanning..."))
            display_lines.append("WIFI: " + (wifi or "scanning..."))

            # If ui.draw.text exists draw lines
            if hasattr(ui, "draw") and hasattr(ui.draw, "text"):
                y = 0
                for line in display_lines:
                    ui.draw.text((0, y), line)
                    y += 10
            else:
                # fallback: try ui.show or ui.set
                if hasattr(ui, "show"):
                    ui.show(display_lines)
                elif hasattr(ui, "set"):
                    ui.set("usb_wifi_watch", {"usb": usb, "wifi": wifi})
                else:
                    logging.info("[usb_wifi_watch] %s | %s", usb, wifi)
        except Exception as e:
            logging.debug("[usb_wifi_watch] ui update failed: %s", e)

        # no extra overlay elements to the framework required, return None
        return None

  def on_unload(self):
      logging.info("[usb_wifi_watch] unloading plugin")
      self.stop_worker()
  
      # Clean up any UI elements from this plugin
      try:
          with ui._lock:
              for element_id in ["usb_wifi_watch_usb", "usb_wifi_watch_wifi", "usb_wifi_watch"]:
                  if hasattr(ui, "remove_element"):
                      ui.remove_element(element_id)
                      logging.debug(f"[usb_wifi_watch] removed UI element {element_id}")
      except Exception as e:
          logging.debug("[usb_wifi_watch] error cleaning UI elements: %s", e)
