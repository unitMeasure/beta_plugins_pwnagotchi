import logging
import subprocess  # Import the subprocess module
import os
import json
import pwnagotchi.plugins as plugins
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
import threading  # Import the threading module for timer

# Static Variables
TAG = "[SigStrV2 Plugin]"

class SigStrV2(plugins.Plugin):
    __author__ = 'bryzz42o, edited by @avipars'
    __version__ = '1.0.6.2'
    __license__ = 'GPL3'
    __name__ = "SigStrV2"
    __description__ = 'Plugin to display signal strength as a bar.'
    __github__ = 'https://github.com/bryzz42o/Pwnagotchi-fsociety-plugins/blob/main/sigstr.py'
    __defaults__ = {
        "enabled": False,
    }

    REFRESH_INTERVAL = 2  # Refresh interval in seconds

    def __init__(self):
        self.strength = 0
        self.symbol_count = 10  # Define the symbol count for the signal strength bar
        self.timer = threading.Timer(self.REFRESH_INTERVAL, self.refresh)  # Create a timer for refreshing

    def on_loaded(self):
        logging.info(TAG + " Plugin loaded")
        self.timer.start()  # Start the timer when the plugin is loaded

    def on_unload(self, ui):
        self.timer.cancel()  # Cancel the timer when the plugin is unloaded
        with ui._lock:
            logging.info(f"[{self.__class__.__name__}] plugin unloaded")
            ui.remove_element('SignalStrength')

    def on_ui_setup(self, ui):
        with ui._lock:
            ui.add_element('SignalStrength', LabeledValue(color=BLACK, label='Signal', value='',
                                                      position=(0, 205),
                                                      label_font=fonts.Bold, text_font=fonts.Medium))

    def on_ui_update(self, ui):
        signal_strength = self.get_wifi_signal_strength()
        if signal_strength is not None:
            self.strength = signal_strength
            signal_bar = self.generate_signal_bar(self.strength)
            ui.set('SignalStrength', signal_bar)

    def refresh(self):
        self.timer = threading.Timer(self.REFRESH_INTERVAL, self.refresh)  # Reset the timer
        self.timer.start()  # Start the timer again
        plugins.notify(f"{TAG} Refreshing signal strength")  # Log a message indicating refresh

    def generate_signal_bar(self, strength_percent):
        # Ensure strength is within 0-100
        strength_percent = max(0, min(100, strength_percent))
        bar_length = int(strength_percent / (100 / self.symbol_count))
        # Use different symbols for better visual clarity (optional)
        filled_char = '█' # Solid block for filled part
        empty_char = '░'  # Shaded block for empty part
        bar_segments = filled_char * bar_length
        empty_segments = empty_char * (self.symbol_count - bar_length)
        signal_bar = f'|{bar_segments}{empty_segments}|'
        return signal_bar

    # FIX 2: More robust parsing and error handling
    def get_wifi_signal_strength(self):
        interface = "wlan0" # Make interface configurable? Maybe later.
        try:
            command = ["iw", "dev", interface, "link"]
            process = subprocess.run(command, capture_output=True, text=True, check=False, timeout=1) # Use subprocess.run, add timeout

            if process.returncode != 0:
                # Log stderr if available and useful, otherwise generic message
                # logging.warning(f"{TAG} 'iw dev {interface} link' command failed with code {process.returncode}. stderr: {process.stderr.strip()}")
                # This often happens when not associated, which is normal. Don't log as error unless needed.
                return None # Interface might be down or not associated

            command_output = process.stdout

            if "Not connected" in command_output:
                # logging.debug(TAG + f" Interface {interface} not connected.")
                return None # Clearly not connected

            if "signal:" in command_output:
                try:
                    signal_part = command_output.split("signal:")[1]
                    dbm_part = signal_part.split(" dBm")[0].strip()
                    signal_strength_dbm = int(dbm_part)

                    # Convert dBm to percentage (common mapping: -90dBm=0%, -40dBm=100%)
                    # Adjust the range (-90, -40) if needed based on observations
                    clamped_dbm = max(-90, min(signal_strength_dbm, -40))
                    percentage = (clamped_dbm + 90) * 2 # Maps 50dB range to 0-100%

                    # Ensure percentage is strictly within 0-100
                    percentage = max(0, min(100, percentage))

                    return percentage

                except (IndexError, ValueError) as parse_err:
                    logging.warning(TAG + f" Could not parse signal strength from 'iw' output: {parse_err}. Output: {command_output}")
                    return None # Parsing failed
            else:
                # logging.debug(TAG + f" 'signal:' not found in 'iw dev {interface} link' output (normal if not associated).")
                return None # No signal information found

        except FileNotFoundError:
            logging.error(TAG + " 'iw' command not found. Is 'iw' package installed?")
            return None
        except subprocess.TimeoutExpired:
             logging.warning(TAG + f" 'iw dev {interface} link' command timed out.")
             return None
        except Exception as e:
            logging.error(TAG + f" Unexpected error getting signal strength: {e}", exc_info=True) # Log full traceback for unexpected errors
            return None