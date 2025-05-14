import logging
import time
from datetime import datetime

import pwnagotchi.plugins as plugins
from pwnagotchi.ui.components import Text, Line, LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts

from PIL import ImageFont

# https://github.com/Sniffleupagus/pwnagotchi_plugins/blob/main/console.py
class better_console(plugins.Plugin):
    __author__ = 'Sniffleupagus'
    __editor__ = 'avipars'
    __version__ = '1.0.0.1'
    __license__ = 'GPL3'
    __description__ = 'An improved console scrolling status updates'
    __defaults__ = {
        "enabled": False
    }
    def __init__(self):
        self._console = [ "%s - Pwnagotchi Console %s" % (datetime.now().strftime('%c'), self.__version__) ]
        self._ui_elements = []       # keep track of UI elements created in on_ui_setup for easy removal in on_unload
        self._last_status = None

    def addConsole(self, msg):
        try:
            logging.debug("console: %s" % msg)
            now = datetime.now().strftime('%X')
            self._console.append('%s %s' % (now, msg))

            if len(self._console) > self.options['showLines']:
                m = self._console.pop(0)
                logging.debug("Removed %s" % m)
                
        except Exception as e:
            logging.exception(repr(e))


    # called when the plugin is loaded
    def on_loaded(self):
        logging.warning("Console options = " % self.options)

        self.options['showLines'] = self.options.get('showLines', 15)

    # called before the plugin is unloaded
    def on_unload(self, ui):
        try:
            # remove UI elements
            i = 0
            with ui._lock:
                for n in self._ui_elements:
                    ui.remove_element(n)
                    logging.info("Removed %s" % repr(n))
                    i += 1
            if i: logging.info("plugin unloaded %d elements" % i)
            
        except Exception as e:
            logging.warning("Unload: %s" % e)

    # called when there's internet connectivity
    def on_internet_available(self, agent):
        pass

    # called to setup the ui elements
    def on_ui_setup(self, ui):
        # add custom UI elements
        pos = self.options.get('position', (20,100))
        self.options['position'] = pos
        color = self.options.get('color', 'Blue')
        font_height = self.options.get('font_size', int(ui._height/60))
        
        confont = ImageFont.truetype(fonts.FONT_NAME, size=font_height)
        ui.add_element('pwn-console', Text(color=color, value='--', position=(pos[0],pos[1]), font=fonts.Small))
        self._ui_elements.append('pwn-console')

    # called when the ui is updated
    def on_ui_update(self, ui):
        # update those elements
        st = ui.get('status')
        if st != "" and st != '...' and st != self._last_status:
            self._last_status = st
            self.addConsole(st)

        ui.set('pwn-console', '\n'.join(self._console[:self.options['showLines']]))


    # called when everything is ready and the main loop is about to start
    def on_ready(self, agent):
        self._agent = agent
        self.addConsole("Ready to pwn")

    # called when the agent is rebooting the board
    def on_rebooting(self, agent):
        self.addConsole("Rebooting.")

    # called when a new handshake is captured, access_point and client_station are json objects
    # if the agent could match the BSSIDs to the current list, otherwise they are just the strings of the BSSIDs
    def on_handshake(self, agent, filename, access_point, client_station):
        self.addConsole("H->%s" % (access_point.get('hostname', "???")))

    # called when a new peer is detected
    def on_peer_detected(self, agent, peer):
        logging.info("Peer: %s" % repr(peer))
        self.addConsole("Peer: %s" % peer.adv.get('name', '???'))

    # called when a known peer is lost
    def on_peer_lost(self, agent, peer):
        logging.info("Peer: %s" % repr(peer))
        self.addConsole("Bye: %s" % peer.adv.get('name', '???'))
        
    def on_bcap_wifi_ap_new(self, agent, event):
        ap = event['data']
        self.addConsole("New AP: %s" % ap['hostname'])

    def on_bcap_wifi_ap_lost(self, agent, event):
        ap = event['data']
        self.addConsole("Bye AP: %s" % ap['hostname'])
