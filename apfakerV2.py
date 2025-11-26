import os
import logging

from random import shuffle
from pwnagotchi import plugins
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
from pwnagotchi.ui import fonts
from time import sleep
from scapy.all import Dot11, Dot11Beacon, Dot11Elt, RadioTap, sendp, RandMAC


class apfakerV2(plugins.Plugin):
    __author__ = '33197631+dadav@users.noreply.github.com'
    __GitHub__ = "https://github.com/dadav/pwnagotchi-custom-plugins/blob/master/apfaker.py"
    __editor__ = 'avipars'
    __version__ = '2.0.5.5'
    __license__ = 'GPL3'
    __description__ = 'Creates fake aps, now with minor improvements'
    __dependencies__ = {
        'pip': ['scapy'],
    }
    __defaults__ = {
        'enabled': False,
        'ssids': ['5G TEST CELL TOWER', 'FBI Van', 'NSA Surveillance Van', 'CIA Listening Post', 'FBI Surveillance Van'],
        'max': 5,
        'repeat': True,
        'password_protected': False,
    }

    def __init__(self):
        self.options = dict()
        self.ready = False

    @staticmethod
    def create_beacon(name, password_protected=False):
        dot11 = Dot11(type=0,
                      subtype=8,
                      addr1='ff:ff:ff:ff:ff:ff',
                      addr2=str(RandMAC()),
                      addr3=str(RandMAC()))

        beacon = Dot11Beacon(cap='ESS+privacy' if password_protected else 'ESS')
        essid = Dot11Elt(ID='SSID',info=name, len=len(name))

        if not password_protected:
            return RadioTap()/dot11/beacon/essid

        rsn = Dot11Elt(ID='RSNinfo', info=(
                       '\x01\x00'
                       '\x00\x0f\xac\x02'
                       '\x02\x00'
                       '\x00\x0f\xac\x04'
                       '\x00\x0f\xac\x02'
                       '\x01\x00'
                       '\x00\x0f\xac\x02'
                       '\x00\x00'))

        return RadioTap()/dot11/beacon/essid/rsn

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
                    logging.error('[apfakerV2] %s', oserr)
                    return
        elif isinstance(self.options['ssids'], list):
            self.ssids = self.options['ssids']
        else:
            logging.error('[apfakerV2] wtf is %s', self.options['ssids'])
            return

        self.ready = True
        logging.info('[apfakerV2] plugin loaded')

    def on_ready(self, agent):
        if not self.ready:
            logging.info('[apfakerV2] not ready')
            return

        shuffle(self.ssids)

        cnt = 0
        base_list = self.ssids.copy()
        while len(self.ssids) <= self.options['max'] and self.options['repeat']:
            self.ssids.extend([f"{ssid}_{cnt}" for ssid in base_list])
            cnt += 1

        frames = list()
        for idx, ssid in enumerate(self.ssids[:self.options['max']]):
            try:
                logging.info('[apfakerV2] creating fake ap with ssid "%s"', ssid)
                frames.append(apfakerV2.create_beacon(ssid, password_protected=self.options['password_protected']))
                agent.view().set('apfake', str(idx + 1))
            except Exception as ex:
                logging.debug('[apfakerV2] %s', ex)

        main_config = agent.config()

        while self.ready:
            # per https://www.4armed.com/blog/forging-wifi-beacon-frames-using-scapy/
            sendp(frames, iface=main_config['main']['iface'], verbose=False)  #frame to be sent every 100 milliseconds until the program is exited  inter=0.100, loop=1
            sleep(max(0.1, len(frames) / 100))

    def on_ui_setup(self, ui):
        with ui._lock:
            ui.add_element('apfake', LabeledValue(color=BLACK, label='F', value='-', position=(ui.width() / 2 + 20, 0),
                           label_font=fonts.Bold, text_font=fonts.Medium))

    def on_before_shutdown(self):
        self.ready = False
        logging.info('[apfakerV2] plugin is shutting down')

    def on_unload(self, ui):
        self.ready = False
        with ui._lock:
            try:
                ui.remove_element('apfake')
            except Exception as e:
                logging.error(f"[{self.__class__.__name__}] unload: %s" % e)
