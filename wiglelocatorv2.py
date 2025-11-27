import requests
import os
import logging
from pwnagotchi.plugins import Plugin


class WigleLocatorV2(Plugin):
    __author__ = 'WPA2'
    __editor__ = 'avipars'
    __version__ = '1.0.0.1'
    __license__ = 'GPL3'
    __description__ = 'Fetches AP location data from WiGLE and saves it with handshake files'

    def __init__(self):
        self.api_key = None  # API key will be set in config.toml
        
    def on_loaded(self):
        if self.is_disabled:
            logging.info("[WigleLocatorV2] plugin loaded but disabled due to 429 error.")
            return
        logging.info(f"[WigleLocatorV2] plugin fully loaded with configuration: {self.options}")

    def on_webhook(self, path, request):
        if not self.ready:
            return "Plugin not ready"

        if path == "/" or not path:
            return self.api_key
          
    def on_config_changed(self, config):
        # Load the WiGLE API key from config.toml
        self.api_key = config.get('main', {}).get('plugins', {}).get('WigleLocatorV2', {}).get('api_key', None)

        if not self.api_key:
            logging.error('[WigleLocatorV2] WiGLE API key not found in config.toml! Please add it under the WigleLocatorV2 section.')
        else:
            logging.info('[WigleLocatorV2] API key successfully loaded.')

    def on_handshake(self, agent, filename, access_point, client_station):
        logging.info(f"[WigleLocatorV2] Handshake event captured. Access Point: {access_point['hostname']}, Client Station: {client_station['mac']}")
        
        if self.is_disabled:
            logging.info("[WigleLocatorV2] Plugin is disabled due to previous rate limit error. Skipping API request.")
            return

        config = agent.config()
        display = agent.view()

        bssid = access_point["mac"]
        essid = access_point["hostname"]

        # Fetch the AP location from WiGLE
        location = self._get_location_from_wigle(bssid)

        if location:
            # Display location on Pwnagotchi UI (if UI is enabled)
            display.set("status", f'AP Location: {location["lat"]}, {location["lon"]}')
            display.update(force=True)
            logging.info(f'[WigleLocatorV2] Location found: Latitude {location["lat"]}, Longitude {location["lon"]}')

            # Save the location information to the handshake folder
            self._save_location(essid, location)
        else:
            logging.warning(f'[WigleLocatorV2] No location found for BSSID: {bssid}')

    def _get_location_from_wigle(self, bssid):
   
        headers = {
            'Authorization': 'Basic ' + self.api_key
        }
        params = {
            'netid': bssid,
        }

        response = requests.get('https://api.wigle.net/api/v2/network/detail', headers=headers, params=params)
        logging.info(f"[WigleLocatorV2] WiGLE API request for BSSID {bssid}, response code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            # Log only the relevant details (SSID, latitude, and longitude)
            if data['success'] and data['results']:
                result = data['results'][0]
                ssid = result.get('ssid', 'N/A')
                trilat = result.get('trilat', 'N/A')
                trilong = result.get('trilong', 'N/A')
                logging.info(f"[WigleLocatorV2] WiGLE API result: SSID={ssid}, Lat={trilat}, Long={trilong}")

                # Return the first result's location details
                return {
                    'lat': trilat,
                    'lon': trilong
                }
            else:
                logging.warning(f'[WigleLocatorV2] No location data found for BSSID: {bssid}')
        elif response.status_code == 429:
            logging.error(f'[WigleLocatorV2] WiGLE API rate limit exceeded. Try again tomorrow. Disabling plugin to prevent further requests.')
            self.is_disabled = True  # Disable the plugin on rate limit exceed to prevent further requests
        else:
            logging.error(f'[WigleLocatorV2] Error fetching WiGLE data: {response.status_code}')
        return None

    def _save_location(self, essid, location):
        # Replace spaces in the ESSID with underscores to avoid issues in file naming
        essid_safe = essid.replace(" ", "_")

        # Dynamically detect the current user's home directory
        user_home = os.path.expanduser('~')
        save_dir = os.path.join(user_home, 'WigleLocatorV2')

        # Ensure the directory exists
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        # Create a file in the custom directory with the ESSID name and location data
        location_file = os.path.join(save_dir, f'{essid_safe}_location.txt')

        logging.info(f"[WigleLocatorV2] Attempting to save location data to {location_file}")
        with open(location_file, 'w') as f:
            f.write(f'ESSID: {essid}\n')
            f.write(f'Latitude: {location["lat"]}\n')
            f.write(f'Longitude: {location["lon"]}\n')
        logging.info(f'[WigleLocatorV2] Successfully saved location data to {location_file}')
