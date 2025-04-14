import logging
import pwnagotchi.plugins as plugins
from pwnagotchi.utils import StatusFile

class pwnStart(plugins.Plugin):
    __author__ = 'avipars'
    __version__ = '0.0.1'
    __license__ = 'GPL3'
    __name__ = 'pwnStart'
    __description__ = 'A plugin to disable auto_tune and fix_services, then enable probenpwn extensions'
    __github__ = 'https://github.com/avipars'
    __defaults__ = {
        "enabled": False,
    }
    def __init__(self):
        self.running = False
        self.status = StatusFile('/var/log/pwnagotchi/pwnStart.status', data={'enabled': False})
        logging.debug("[pwnStart] plugin initialized")
    
    def on_loaded(self):
        logging.info("[pwnStart] plugin loaded")
        self.running = True
        
        # Update status file
        self.status.update(data={'enabled': True})
        
        # Disable auto_tune
        if hasattr(self.options, 'auto_tune') and self.options['auto_tune']:
            logging.info("[pwnStart] Disabling auto_tune")
            self.options['auto_tune'] = False
        else:
            logging.info("[pwnStart] auto_tune was already disabled or not found")
            
        # Disable fix_services
        if hasattr(self.options, 'fix_services') and self.options['fix_services']:
            logging.info("[pwnStart] Disabling fix_services")
            self.options['fix_services'] = False
        else:
            logging.info("[pwnStart] fix_services was already disabled or not found")
            
        # Enable probenpwn extensions
        try:
            logging.info("[pwnStart] Enabling probenpwn extensions")
            # This could be modified based on how the probenpwn extensions need to be enabled
            # Method 1: If probenpwn is a separate plugin
            if 'probenpwn' in self.options:
                self.options['probenpwn']['enabled'] = True
                logging.info("[pwnStart] Enabled probenpwn via options")
            
            # Method 2: If probenpwn needs system configuration
            import subprocess
            subprocess.run(['systemctl', 'enable', 'probenpwn.service'], check=True)
            subprocess.run(['systemctl', 'start', 'probenpwn.service'], check=True)
            logging.info("[pwnStart] Enabled probenpwn via systemd")
            
        except Exception as e:
            logging.error(f"[pwnStart] Error enabling probenpwn extensions: {e}")
            
        logging.info("[pwnStart] Configuration complete!")
    
    def on_unload(self, ui):
        logging.info("[pwnStart] plugin unloaded")
        self.running = False
        self.status.update(data={'enabled': False})
    
    def on_webhook(self, path, request):
        # Optional: add a webhook to check status or toggle settings
        if request.method == 'GET' and path == '/plugins/pwnStart/status':
            return {'enabled': self.running}
        return None