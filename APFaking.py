import os
import logging

from random import shuffle
from pwnagotchi import plugins
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
from pwnagotchi.ui import fonts
from time import sleep
from scapy.all import Dot11, Dot11Beacon, Dot11Elt, RadioTap, sendp, RandMAC
import threading


class APFaking(plugins.Plugin):
    __author__ = '33197631+dadav@users.noreply.github.com'
    __editor__ = 'avipars'
    __version__ = '2.0.4.4'
    __license__ = 'GPL3'
    __description__ = 'Creates fake aps.'
    __dependencies__ = {
        'pip': ['scapy'],
    }
    __defaults__ = {
        'ssids': ['5G TEST CELL TOWER', 'FBI Van', 'NSA Surveillance Van', 'CIA Listening Post', 'FBI Surveillance Van'],
        'max': 10,
        'enabled': False,
        'repeat': True,
        'password_protected': False,
    }

    def __init__(self):
        self.options = dict()
        self.shutdown = False
        self.ready = True
        self.ap_status = "I"
        self.turn_off = False

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
            logging.error('[APFaking] loading as str %s', self.options['ssids'])
            path = self.options['ssids']

            if not os.path.exists(path):
                self.ssids = [path]
            else:
                try:
                    with open(path) as wordlist:
                        self.ssids = wordlist.read().split()
                except OSError as oserr:
                    logging.error('[APFaking] %s', oserr)
                    return
        elif isinstance(self.options['ssids'], list):
            self.ssids = self.options['ssids']
            logging.error('[APFaking] loading as list %s', self.options['ssids'])

        else:
            logging.error('[APFaking] wtf is %s', self.options['ssids'])
            return

        self.ready = True
        logging.info('[APFaking] plugin loaded')
        self.shutdown = False

    def on_ui_update(self, ui):
        ui.set("apfaking", "%s" % (self.ap_status))

    def on_ready(self, agent):
        if not self.ready:
            logging.info('[APFaking] exiting ready, shutdown')
            return
            
        self.shutdown = False
        self.turn_off = False
        self.worker = threading.Thread(
            target=self._run,
            args=(agent,),
            daemon=True)
        self.worker.start()

        logging.info('[APFaking] worker thread started')
        shuffle(self.ssids)

        cnt = 0
        base_list = self.ssids.copy()
        while len(self.ssids) <= self.options['max'] and self.options['repeat']:
            self.ssids.extend([f"{ssid}_{cnt}" for ssid in base_list])
            cnt += 1

        frames = list()
        for idx, ssid in enumerate(self.ssids[:self.options['max']]):
            try:
                logging.info('[APFaking] creating fake ap with ssid "%s"', ssid)
                frames.append(APFaking.create_beacon(ssid, password_protected=self.options['password_protected']))
                # agent.view().set('apfaking', str(idx + 1))
                self.ap_status =  str(idx + 1)
            except Exception as ex:
                logging.debug('[APFaking] %s', ex)

        main_config = agent.config()

        while not self.shutdown:
            if self.turn_off:
                self.ap_status =  "U"
                logging.info('[APFaking] plugin turning off')
                break
            sendp(frames, iface=main_config['main']['iface'], verbose=False)
            sleep(max(0.1, len(frames) / 100))

    def on_before_shutdown(self):
        self.turn_off = True
        self.ap_status =  "B"
        self.shutdown = True
        logging.info('[APFaking] plugin before shutdown')

    def on_ui_setup(self, ui):
        with ui._lock:
            try:
                ui.add_element('apfaking', LabeledValue(color=BLACK, label='F', value='S', position=(int(ui.width() / 2 + 20), 0),
                            label_font=fonts.Bold, text_font=fonts.Medium))
            except Exception as ex:
                logging.debug('[APFaking] %s', ex) 

    def on_unload(self, ui):
        self.turn_off = True
        self.shutdown = True
        self.ap_status =  "U"
        with ui._lock:
            try:
                ui.remove_element('apfaking')
                logging.info('[APFaking] plugin is unloading')
            except Exception as ex:
                logging.debug('[APFaking] %s', ex)
                
    def _run(self, agent):
        shuffle(self.ssids)
    
        cnt = 0
        base_list = self.ssids.copy()
        while len(self.ssids) <= self.options['max'] and self.options['repeat']:
            self.ssids.extend([f"{ssid}_{cnt}" for ssid in base_list])
            cnt += 1
    
        frames = []
        for idx, ssid in enumerate(self.ssids[:self.options['max']]):
            try:
                logging.info('[APFaking] creating fake ap with ssid "%s"', ssid)
                frames.append(
                    APFaking.create_beacon(
                        ssid,
                        password_protected=self.options['password_protected']
                    )
                )
                self.ap_status = str(idx + 1)
            except Exception as ex:
                logging.debug('[APFaking] %s', ex)
    
        iface = agent.config()['main']['iface']
    
        while not self.shutdown:
            if self.turn_off:
                self.ap_status = "U"
                break
    
            sendp(frames, iface=iface, verbose=False)
            sleep(max(0.1, len(frames) / 100))


