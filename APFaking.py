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
    __version__ = '2.0.4.5'
    __license__ = 'GPL3'
    __description__ = 'Creates fake aps. Useful to confuse wardrivers and for testing. '
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
    #https://github.com/dadav/pwnagotchi-custom-plugins/blob/master/apfaker.py

    def __init__(self):
        self.options = {}
        
        self.ready = False
        self.ap_status = "I"
        self._thread = None
        self._stop_event = threading.Event()
        self._frames = []

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
        ssids_opt = self.options.get('ssids', None)

        if isinstance(ssids_opt, str):
            if os.path.exists(ssids_opt):
                try:
                    with open(ssids_opt) as f:
                        self.ssids = f.read().split()
                except OSError as e:
                    logging.error('[apfaker] %s', e)
                    return
            else:
                self.ssids = [ssids_opt]

        elif isinstance(ssids_opt, list):
            self.ssids = ssids_opt
        else:
            logging.error('[apfaker] invalid ssids option')
            return

        self.ready = True
        logging.info('[apfaker] plugin loaded')


    def on_ui_update(self, ui):
        ui.set("apfaking", "%s" % (self.ap_status))

    def on_ready(self, agent):
        if not self.ready:
            logging.info('[APFaking] exiting ready, shutdown')
            return


        logging.info('[APFaking] on_ready started')
        shuffle(self.ssids)

        cnt = 0
        base_list = self.ssids.copy()

        self.ap_status =  str(cnt)

        while len(self.ssids) <= self.options['max'] and self.options['repeat']:
            self.ssids.extend([f"{ssid}_{cnt}" for ssid in base_list])
            cnt += 1

        self._frames.clear()
        max_num = self.options.get('max', 10)
        for idx, ssid in enumerate(self.ssids[:max_num]):
            try:
                logging.info('[APFaking] creating fake ap with ssid "%s"', ssid)

                frame = self.create_beacon(
                    ssid,
                    password_protected=self.options['password_protected']
                )
                self._frames.append(frame)
                # agent.view().set('apfaking', str(idx + 1))
                self.ap_status =  str(idx + 1)
            except Exception as ex:
                logging.debug('[APFaking] %s', ex)

        iface = agent.config()['main']['iface']

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._beacon_loop,
            args=(iface,),
            daemon=True
        )
        self._thread.start()

        logging.info('[apfaker] beacon thread started')

    def _beacon_loop(self, iface):
        while not self._stop_event.is_set():
            sendp(self._frames, iface=iface, verbose=False)
            sleep(max(0.1, len(self._frames) / 100))

        logging.info('[apfaker] beacon thread stopped')

    def _stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._thread = None

    def on_before_shutdown(self):
        self.ap_status =  "B"
        self._stop()
        logging.info('[APFaking] plugin before shutdown')

    def on_ui_setup(self, ui):
        with ui._lock:
            try:
                ui.add_element('apfaking', LabeledValue(color=BLACK, label='F', value='S', position=(int(ui.width() / 2 + 20), 0),
                            label_font=fonts.Bold, text_font=fonts.Medium))
            except Exception as ex:
                logging.debug('[APFaking] %s', ex) 

    def on_unload(self, ui):
        self.ap_status =  "U"

        self._stop()
        with ui._lock:
            try:
                ui.remove_element('apfaking')
                logging.info('[APFaking] plugin is unloading')
            except Exception as ex:
                logging.debug('[APFaking] %s', ex)
                