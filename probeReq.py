import logging
from PIL import ImageFont

import pwnagotchi.plugins as plugins
from pwnagotchi.ui.components import Text
from pwnagotchi.ui.view import BLACK
from pwnagotchi.bettercap import Client

# Load a font directly instead of using fonts.Small, so you control the
# exact pixel size rather than whatever pwnagotchi's presets give you.
_TINY_FONT = ImageFont.truetype(
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 8
)

class probeReq(plugins.Plugin):
    __GitHub__ = "https://github.com/unitMeasure/pwn-plugins/"
    __author__ = "avipars"
    __editor__ = "avipars"
    __version__ = "0.0.2.5"
    __license__ = "GPL3"
    __description__ = "Listens for Wi-Fi probe requests, displays them on screen and logs them."
    __name__ = "probeReq"
    __defaults__ = {
        "enabled": False,
        "verbose": False,
        "logging": False,
    }

    def __init__(self):
        self.ready = False
        self.title = ""
        self.running = True
        self.pr_status = "Waiting"
        self.pos_x = 0
        self.pos_y = 63
        self.show_verbose = False
        self.log_results = False
        
    def on_loaded(self):
        self.pr_status = "Waiting."
        self.show_verbose = self.options.get("verbose", False)
        self.log_results = self.options.get("logging", False)

    def on_ready(self, agent):
        self.pr_status = "Waiting.."

    def on_ui_setup(self, ui):
        try:
            if "pos_x" in self.options:
                self.pos_x = int(self.options.get("pos_x", 0))
            if "pos_y" in self.options:
                self.pos_y = int(self.options.get("pos_y", 63))

            # font_height = self.options.get('font_size', int(ui._height/60))
            # confont = ImageFont.truetype(fonts.FONT_NAME, size=font_height)

            logging.info(f"[{self.__class__.__name__}] pos_x {self.pos_x} pos_y {self.pos_y}")
            # label_spacing=3
            # ui.add_element(
            #     "pr_status",
            #     LabeledValue(
            #         color=BLACK,
            #         label="",
            #         value=f"[{self.__class__.__name__}]: Active",
            #         position=(self.pos_x, self.pos_y),
            #         label_font=fonts.Small,
            #         text_font=fonts.Small,
            #         label_spacing=label_spacing
            #     )
            # )
          
            ui.add_element(
                "pr_status",
                Text(
                    color=BLACK,
                    value="Active",
                    position=(self.pos_x, self.pos_y),
                    font=_TINY_FONT,
                ),)
        
        except Exception as e:
            logging.debug(f"[{self.__class__.__name__}]: Error on_ui_setup: {e}")

    def on_ui_update(self, ui):
        ui.set("pr_status", "%s" % (self.pr_status))

    def on_bcap_wifi_client_probe(self, agent, event):
        """WIFI CLIENT PROBE REQUEST"""
        if not self.running:
            if self.log_results:
                logging.info(f"[{self.__class__.__name__}]: plugin stopped running")
            return

        probe = event["data"]
        d_name = (probe.get('essid') or '')[:16] # essid truncated
        
        if self.log_results:
            logging.info(f"[{self.__class__.__name__}]: Probe %s" % (probe))
        
        stat = "pr:%s" % d_name # limit essid to 20 chars
        if self.show_verbose:
            stat += " rssi:%s" % probe["rssi"]
            vend = probe["vendor"]

            if vend and len(vend) >= 1: # has a vendor
               stat += "\n" + "v:%s" % vend[0:15] # limit vendor to 15 chars

            stat += "\n" + "mac:%s" % probe["mac"] # full mac address
        
        self.pr_status = stat
       
    def on_unload(self, ui):
        self.running = False
        with ui._lock:
            try:
                ui.remove_element("pr_status")
                if self.log_results:
                    logging.info(f"[{self.__class__.__name__}] plugin unloaded")
            except Exception as e:
                logging.error(f"[{self.__class__.__name__}] unload: %s" % e)
