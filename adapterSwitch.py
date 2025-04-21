import logging
import os
import subprocess
import time # Added for sleep after modeswitch
import re   # Added for parsing lsusb output
import pwnagotchi.plugins as plugins

# Configure logging
log = logging.getLogger(__name__)

class adapterSwitch(plugins.Plugin):
    __author__ = 'avipars'
    __version__ = '0.0.1'
    __license__ = 'GPL3'
    __description__ = 'Automatically switches between internal (wlan0) and external (wlan1) WiFi adapters, using wlan0mon as the monitor interface.'
    __github__ = 'https://github.com/avipars'
    __defaults__ = {
        "enabled": False
    }
    def __init__(self):
        log.debug("External Adapter Switcher plugin created")
        self.external_adapter = 'wlan1'
        self.internal_adapter = 'wlan0'
        self.monitor_interface = 'wlan0mon' # Pwnagotchi expects this
        self.temp_internal_name = 'wlan_temp' # Temporary name for disabled internal adapter
        self.active_adapter_type = None # 'internal' or 'external'

        # --- USB Modeswitch Configuration ---
        # Vendor/Product ID of the adapter when in CD-ROM mode
        self.cdrom_vid = '0bda'
        self.cdrom_pid = '1a2b'
        # The modeswitch command - assuming Pwnagotchi runs as root
        self.modeswitch_cmd = ['usb_modeswitch', '-v', self.cdrom_vid, '-p', self.cdrom_pid, '-K']
        # Time to wait after modeswitch for device re-enumeration (seconds)
        self.modeswitch_delay = 5

    def _run_cmd(self, command, check=False):
        """Runs a shell command."""
        log.debug(f"Running command: {' '.join(command)}")
        try:
            # Ensure Pwnagotchi's environment is used if necessary (though usually not needed for these commands)
            env = os.environ.copy()
            result = subprocess.run(command, shell=False, capture_output=True, text=True, check=check, env=env)
            # Log stdout/stderr only if they contain data
            stdout = result.stdout.strip() if result.stdout else ""
            stderr = result.stderr.strip() if result.stderr else ""
            if stdout:
                log.debug(f"Command stdout: {stdout}")
            if stderr:
                # Log stderr as warning if command potentially failed (non-zero exit but check=False)
                level = logging.WARNING if result.returncode != 0 and not check else logging.DEBUG
                log.log(level, f"Command stderr: {stderr}")
            return result
        except subprocess.CalledProcessError as e:
            # This happens when check=True and the command fails
            log.error(f"Command failed with exit code {e.returncode}: {' '.join(command)}")
            stderr = e.stderr.strip() if e.stderr else ""
            if stderr:
                log.error(f"Stderr: {stderr}")
            return None
        except Exception as e:
            log.error(f"Error running command {' '.join(command)}: {e}")
            return None

    def _check_interface_exists(self, iface_name):
        """Checks if a network interface exists using ip link."""
        # Using 'ip link' is generally more reliable than 'iwconfig' for just checking existence
        result = self._run_cmd(['ip', 'link', 'show', iface_name])
        # 'ip link show <iface>' returns 0 if exists, non-zero otherwise
        return result is not None and result.returncode == 0

    def _kill_interfering_processes(self):
        """Runs 'airmon-ng check kill'."""
        log.info("Running airmon-ng check kill...")
        self._run_cmd(['airmon-ng', 'check', 'kill'])
        time.sleep(1) # Give processes time to die

    def _set_interface_state(self, iface_name, state):
        """Sets interface state up or down using ip link."""
        # Use 'ip link set' instead of 'ifconfig'
        log.info(f"Setting interface {iface_name} {state}")
        if self._check_interface_exists(iface_name):
             self._run_cmd(['ip', 'link', 'set', iface_name, state])
             time.sleep(0.5) # Small delay
        else:
            log.warning(f"Interface {iface_name} not found, cannot set state to {state}.")


    def _rename_interface(self, old_name, new_name):
        """Renames an interface using ip link."""
         # Use 'ip link set name' instead of 'iw dev set name'
        if self._check_interface_exists(old_name):
            log.info(f"Renaming interface {old_name} to {new_name}")
            # Interface must be down to rename with 'ip link'
            self._set_interface_state(old_name, 'down')
            result = self._run_cmd(['ip', 'link', 'set', old_name, 'name', new_name])
            time.sleep(0.5) # Small delay
            # Check if the new name exists now
            if self._check_interface_exists(new_name):
                 log.debug(f"Successfully renamed {old_name} to {new_name}")
                 return True
            else:
                 log.error(f"Failed to rename {old_name} to {new_name}. Interface {new_name} not found after command.")
                 # Try to bring the old interface back up if rename failed?
                 self._set_interface_state(old_name, 'up')
                 return False
        else:
             log.warning(f"Interface {old_name} not found, cannot rename.")
             return False


    def _start_monitor_mode(self, iface_name):
        """Puts the specified interface into monitor mode using airmon-ng."""
        if self._check_interface_exists(iface_name):
            log.info(f"Putting interface {iface_name} into monitor mode...")
            self._set_interface_state(iface_name, 'up')
            result = self._run_cmd(['airmon-ng', 'start', iface_name])
            time.sleep(1) # Give airmon-ng time to work

            # Check if monitor interface (wlan0mon) exists *after* airmon-ng command
            # This is crucial to know if airmon-ng created it or if we need to rename
            if self._check_interface_exists(self.monitor_interface):
                log.info(f"Monitor interface {self.monitor_interface} found after airmon-ng start.")
                return True # Assumes airmon-ng created/renamed to wlan0mon directly or indirectly
            else:
                # If wlan0mon doesn't exist, maybe airmon-ng modified the original interface?
                # Or created something like wlanXmon? This plugin expects wlan0mon.
                # Let's stick to the original script's implied logic: rename *after* start.
                log.warning(f"{self.monitor_interface} not found immediately after airmon-ng start {iface_name}. Assuming manual rename is needed.")
                # The rename happens in the _switch_to_* methods based on original logic
                return True # Proceed, assuming rename will happen next
        else:
            log.warning(f"Interface {iface_name} not found, cannot start monitor mode.")
            return False

    def _stop_monitor_mode(self, monitor_iface):
        """Stops monitor mode on the specified interface."""
        if self._check_interface_exists(monitor_iface):
            log.info(f"Stopping monitor mode on {monitor_iface}...")
            self._run_cmd(['airmon-ng', 'stop', monitor_iface])
            time.sleep(1) # Give airmon-ng time to work
        else:
            log.debug(f"Monitor interface {monitor_iface} not found, skipping stop command.")


    def _switch_to_external(self):
        """Switches Pwnagotchi to use the external adapter."""
        log.info("Attempting switch to external WiFi adapter...")
        self.active_adapter_type = None # Mark as in-transition

        # Check if external adapter exists *before* proceeding
        if not self._check_interface_exists(self.external_adapter):
            log.error(f"External adapter {self.external_adapter} not found. Cannot switch.")
            return False

        self._kill_interfering_processes()
        self._stop_monitor_mode(self.monitor_interface) # Stop existing monitor if any

        # Take down and rename internal adapter
        renamed_internal = False
        if self._check_interface_exists(self.internal_adapter):
            self._set_interface_state(self.internal_adapter, 'down')
            renamed_internal = self._rename_interface(self.internal_adapter, self.temp_internal_name)
            if not renamed_internal:
                log.warning(f"Could not rename {self.internal_adapter} to {self.temp_internal_name}. Proceeding with caution.")

        # Configure external adapter
        self._set_interface_state(self.external_adapter, 'down') # Ensure down before airmon/rename
        if self._start_monitor_mode(self.external_adapter):
            # Rename the external adapter (now in monitor mode) to pwnagotchi's expected name
            renamed_external = self._rename_interface(self.external_adapter, self.monitor_interface)
            if renamed_external:
                self._set_interface_state(self.monitor_interface, 'up') # Bring up the renamed monitor interface
                log.info(f"Successfully switched to external adapter ({self.external_adapter} is now {self.monitor_interface}).")
                self.active_adapter_type = 'external'
                return True
            else:
                 log.error(f"Failed to rename {self.external_adapter} to {self.monitor_interface} after monitor mode.")
                 # Attempt recovery: Rename internal back if needed, bring external back up
                 if renamed_internal:
                    self._rename_interface(self.temp_internal_name, self.internal_adapter)
                 self._set_interface_state(self.external_adapter, 'up') # Bring original external back up

        else:
            log.error(f"Failed to start monitor mode on external adapter {self.external_adapter}.")
            if renamed_internal: # Rename internal back if it was temp'd
                self._rename_interface(self.temp_internal_name, self.internal_adapter)
                self._set_interface_state(self.internal_adapter, 'up')

        log.error("Failed to complete switch to external adapter.")
        # If failed, try to ensure internal is active as fallback
        self._ensure_internal_active()
        return False


    def _switch_to_internal(self):
        """Switches Pwnagotchi back to use the internal adapter."""
        log.info("Attempting switch to internal WiFi adapter...")
        self.active_adapter_type = None # Mark as in-transition

        self._kill_interfering_processes()
        self._stop_monitor_mode(self.monitor_interface) # Stop existing monitor if any

        # If monitor interface exists, try renaming it back to external (might fail if removed)
        if self._check_interface_exists(self.monitor_interface):
             self._set_interface_state(self.monitor_interface, 'down')
             self._rename_interface(self.monitor_interface, self.external_adapter) # Ignore result

        # Check if internal adapter needs renaming back from temp name
        internal_ready = False
        if self._check_interface_exists(self.temp_internal_name):
            log.info(f"Reactivating internal adapter {self.internal_adapter} from {self.temp_internal_name}")
            renamed_internal = self._rename_interface(self.temp_internal_name, self.internal_adapter)
            if renamed_internal:
                internal_ready = True
            else:
                 log.error(f"Failed to rename {self.temp_internal_name} back to {self.internal_adapter}. Cannot activate internal.")
                 return False # Critical failure
        elif self._check_interface_exists(self.internal_adapter):
            log.debug(f"Internal adapter {self.internal_adapter} already exists.")
            internal_ready = True # Internal adapter exists with correct name
        else:
             log.error(f"Neither {self.internal_adapter} nor {self.temp_internal_name} found. Cannot activate internal adapter.")
             return False # Critical failure

        if not internal_ready:
            log.error("Internal adapter is not ready. Aborting switch.")
            return False

        # Activate internal adapter and put it in monitor mode
        self._set_interface_state(self.internal_adapter, 'up')
        if self._start_monitor_mode(self.internal_adapter):
            # Rename the internal adapter (now in monitor mode) to pwnagotchi's expected name
            renamed_monitor = self._rename_interface(self.internal_adapter, self.monitor_interface)
            if renamed_monitor:
                 self._set_interface_state(self.monitor_interface, 'up')
                 log.info(f"Successfully reverted to internal adapter ({self.internal_adapter} is now {self.monitor_interface}).")
                 self.active_adapter_type = 'internal'
                 return True
            else:
                 log.error(f"Failed to rename {self.internal_adapter} to {self.monitor_interface} after monitor mode.")
                 # Attempt to bring internal back up under original name
                 self._set_interface_state(self.internal_adapter, 'up')
        else:
            log.error(f"Failed to start monitor mode on internal adapter {self.internal_adapter}.")

        log.error("Failed to complete switch to internal adapter.")
        return False

    def _ensure_internal_active(self):
        """Tries to make sure the internal adapter is active and in monitor mode."""
        log.info("Attempting to ensure internal adapter is the active monitor...")
        # Check if already correct
        if self.active_adapter_type == 'internal' and self._check_interface_exists(self.monitor_interface):
            log.debug("Internal adapter already seems active and monitor interface exists.")
            return True
        # Attempt a full switch to internal
        return self._switch_to_internal()


    def on_loaded(self):
        """Called when the plugin is loaded. Includes USB modeswitch check."""
        log.info("External Adapter Switcher plugin loaded.")

        # --- USB Modeswitch Check ---
        log.info(f"Checking USB devices for CD-ROM mode ({self.cdrom_vid}:{self.cdrom_pid})...")
        try:
            lsusb_result = self._run_cmd(['lsusb'])
            if lsusb_result and lsusb_result.returncode == 0:
                # Use regex to find the ID VVVV:PPPP pattern
                search_pattern = re.compile(f"ID\\s+{self.cdrom_vid}:{self.cdrom_pid}", re.IGNORECASE)
                if search_pattern.search(lsusb_result.stdout):
                    log.info(f"Adapter found in CD-ROM mode ({self.cdrom_vid}:{self.cdrom_pid}). Attempting USB modeswitch...")
                    # Execute the modeswitch command
                    switch_result = self._run_cmd(self.modeswitch_cmd)
                    if switch_result and switch_result.returncode == 0:
                        log.info(f"USB modeswitch command executed successfully. Waiting {self.modeswitch_delay}s for device re-enumeration...")
                        time.sleep(self.modeswitch_delay) # Wait
                        log.info("Device should have re-enumerated. Proceeding...")
                    else:
                        log.error("USB modeswitch command failed or returned an error. External adapter might not be available.")
                else:
                    log.info("Adapter not found in CD-ROM mode via lsusb.")
            else:
                log.warning("Could not execute lsusb or it failed. Skipping CD-ROM mode check.")
        except Exception as e:
            log.error(f"Error during USB modeswitch check: {e}")
        # --- End USB Modeswitch Check ---

        # Perform initial check/switch after potential modeswitch
        log.info("Performing initial adapter check/switch...")
        # Agent object isn't available yet in on_loaded
        self.check_and_switch(None)


    def on_unload(self, ui):
        """Called when the plugin is unloaded."""
        log.info("External Adapter Switcher plugin unloading. Attempting revert to internal adapter.")
        try:
            # Ensure we revert to internal WiFi when the plugin stops
            self._ensure_internal_active()
            log.info("Revert to internal adapter on unload finished.")
        except Exception as e:
            log.error(f"Error during on_unload cleanup: {e}")

    def on_ready(self, agent):
        """Called once the agent is ready (after on_loaded)."""
        # A check here ensures interfaces are settled after potential modeswitch and pwnagotchi startup
        log.info("Agent ready. Running adapter check/switch.")
        self.check_and_switch(agent)

    def on_period(self, agent, epoch, epoch_data):
        """Called periodically."""
        # Minimal logging for periodic checks to avoid spam
        log.debug("Periodic check...")
        self.check_and_switch(agent)

    def check_and_switch(self, agent): # Added agent parameter, can be None
        """Checks for adapter presence and initiates switch if needed."""
        external_present = self._check_interface_exists(self.external_adapter)
        internal_is_temp = self._check_interface_exists(self.temp_internal_name)
        monitor_iface_present = self._check_interface_exists(self.monitor_interface)

        # Simplified logging for periodic checks
        # log.debug(f"Check: Ext={external_present}, IntTmp={internal_is_temp}, Mon={monitor_iface_present}, Active={self.active_adapter_type}")

        if external_present:
            # External adapter is plugged in.
            if self.active_adapter_type != 'external':
                log.info(f"External adapter {self.external_adapter} detected, but not marked active. Attempting switch TO external.")
                self._switch_to_external()
                # Pwnagotchi might need a restart if bettercap/monitor doesn't automatically re-attach.
                # Consider adding agent.restart() here if needed, but test implications.
                # if switched and agent: agent.restart('External adapter switch')
            elif not monitor_iface_present:
                # External is supposed to be active, but monitor iface is gone? Try to fix.
                log.warning(f"External adapter should be active, but {self.monitor_interface} is missing! Re-attempting switch TO external.")
                self._switch_to_external()

        else:
            # External adapter is NOT plugged in.
            if self.active_adapter_type == 'external' or internal_is_temp:
                # We were using external, or internal is still disabled -> switch back to internal
                log.info(f"External adapter {self.external_adapter} NOT detected. Attempting switch TO internal.")
                self._switch_to_internal()
                # if switched and agent: agent.restart('Internal adapter switch')
            elif self.active_adapter_type != 'internal':
                # Not external, not internal_temp, not marked internal -> Ensure internal is active (Initial state or recovery)
                 log.info(f"External adapter {self.external_adapter} NOT detected and state unclear. Ensuring internal adapter is active.")
                 self._ensure_internal_active()
            elif not monitor_iface_present:
                 # Internal is supposed to be active, but monitor iface is gone? Try to fix.
                 log.warning(f"Internal adapter should be active, but {self.monitor_interface} is missing! Re-attempting switch TO internal.")
                 self._ensure_internal_active() # _ensure_internal_active calls _switch_to_internal