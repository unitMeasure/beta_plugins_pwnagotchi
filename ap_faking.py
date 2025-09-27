import os
import logging
import threading
from random import shuffle
from pwnagotchi import plugins
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
from pwnagotchi.ui import fonts
from time import sleep
from scapy.all import Dot11, Dot11Beacon, Dot11Elt, RadioTap, sendp, RandMAC


class ApFaking(plugins.Plugin):
    __author__ = '33197631+dadav@users.noreply.github.com'
    __version__ = '2.0.4.1'
    __license__ = 'GPL3'
    __description__ = 'Creates fake aps. Edited by avipars - beta may not work'
    __dependencies__ = {
        'pip': ['scapy'],
    }
    __defaults__ = {
        'enabled': False,
        'ssids': ['5G TEST CELL TOWER', 'FBI Van', 'NSA Surveillance Van', 'CIA Listening Post', 'FBI Surveillance Van'],
        'max': 10,
        'repeat': True,
        'password_protected': False,
    }

    def __init__(self):
        self.options = dict()
        self.ready = False
        self.shutdown = False
        self._thread = None
        self._frames = []
        self._iface = None

    @staticmethod
    def create_beacon(name, password_protected=False):
        dot11 = Dot11(type=0,
                      subtype=8,
                      addr1='ff:ff:ff:ff:ff:ff',
                      addr2=str(RandMAC()),
                      addr3=str(RandMAC()))

        beacon = Dot11Beacon(cap='ESS+privacy' if password_protected else 'ESS')
        essid = Dot11Elt(ID='SSID', info=name, len=len(name))

        if not password_protected:
            return RadioTap() / dot11 / beacon / essid

        rsn = Dot11Elt(ID='RSNinfo', info=(
            '\x01\x00'
            '\x00\x0f\xac\x02'
            '\x02\x00'
            '\x00\x0f\xac\x04'
            '\x00\x0f\xac\x02'
            '\x01\x00'
            '\x00\x0f\xac\x02'
            '\x00\x00'))

        return RadioTap() / dot11 / beacon / essid / rsn

    def on_loaded(self):
        if isinstance(self.options['ssids'], str):
            path = self.options['ssids']

            if not os.path.exists(path):
                self.ssids = [path]
            else:
                try:
                    with open(path) as wordlist:
                        self.ssids = wordlist.read().split()
                except OSError as oserr:
                    logging.error('[ApFaking] %s', oserr)
                    return
        elif isinstance(self.options['ssids'], list):
            self.ssids = self.options['ssids']
        else:
            logging.error('[ApFaking] wtf is %s', self.options['ssids'])
            return

        self.ready = True
        logging.info('[ApFaking] plugin loaded')

    def _prepare_frames(self, main_config):
        shuffle(self.ssids)
        cnt = 0
        base_list = self.ssids.copy()
        while len(self.ssids) <= self.options['max'] and self.options['repeat']:
            self.ssids.extend([f"{ssid}_{cnt}" for ssid in base_list])
            cnt += 1

        frames = list()
        for idx, ssid in enumerate(self.ssids[:self.options['max']]):
            try:
                logging.info('[ApFaking] creating fake ap with ssid "%s"', ssid)
                frames.append(ApFaking.create_beacon(ssid, password_protected=self.options['password_protected']))
            except Exception as ex:
                logging.debug('[ApFaking] %s', ex)

        self._frames = frames
        self._iface = main_config['main'].get('iface')

    def _broadcast_loop(self, agent):
        # run in a separate thread so unloading can stop it
        try:
            main_config = agent.config()
            self._prepare_frames(main_config)

            # If no frames or iface, just exit
            if not self._frames or not self._iface:
                logging.warning('[ApFaking] no frames or iface configured, not broadcasting')
                return

            # Broadcast until shutdown is requested
            while not self.shutdown:
                try:
                    sendp(self._frames, iface=self._iface, verbose=False)
                except Exception as e:
                    logging.debug('[ApFaking] sendp failed: %s', e)
                # throttling sleep: proportional to number of frames but not less than 0.1s
                sleep(max(0.1, len(self._frames) / 100))
        except Exception as e:
            logging.exception('[ApFaking] unexpected error in broadcast thread: %s', e)
        finally:
            logging.info('[ApFaking] broadcast loop exiting')

    def on_ready(self, agent):
        if not self.ready:
            return

        # ensure any previous thread is stopped
        self.shutdown = False
        if self._thread and self._thread.is_alive():
            # try to stop previous thread gracefully
            self.shutdown = True
            self._thread.join(timeout=2)

        # start new thread for broadcasting
        self._thread = threading.Thread(target=self._broadcast_loop, args=(agent,))
        self._thread.daemon = True
        self._thread.start()
        logging.info('[ApFaking] broadcast thread started')

    def on_before_shutdown(self):
        logging.info('[ApFaking] on_before_shutdown called, signaling thread to stop')
        self.shutdown = True
        if self._thread:
            self._thread.join(timeout=3)
            logging.info('[ApFaking] broadcast thread joined')

    # on_unload signature may vary by framework. accept an optional param
    def on_unload(self, ui=None):
        logging.info('[ApFaking] on_unload called, stopping broadcaster and cleaning UI')
        # signal shutdown and join thread
        self.shutdown = True
        if self._thread:
            self._thread.join(timeout=3)
            logging.info('[ApFaking] broadcast thread joined on unload')
        # remove UI element if possible
        if ui:
            try:
                with ui._lock:
                    ui.remove_element('apfake')
            except Exception as e:
                logging.debug('[ApFaking] error removing ui element: %s', e)

    def on_ui_setup(self, ui):
        with ui._lock:
            ui.add_element('apfake', LabeledValue(color=BLACK, label='F', value='-', position=(ui.width() / 2 + 20, 0),
                           label_font=fonts.Bold, text_font=fonts.Medium))
