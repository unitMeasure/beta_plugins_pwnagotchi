import logging
import pwnagotchi.plugins as plugins

class pwnStart(plugins.Plugin):
    __author__ = 'avipars'
    __version__ = '0.0.4'
    __license__ = 'GPL3'
    __name__ = 'pwnStart'
    __description__ = 'A plugin to disable auto_tune and fix_services, then enable probenpwn extensions'
    __github__ = 'https://github.com/avipars'
    __defaults__ = {
        "enabled": False
    }
    def __init__(self):
        self.running = False
        logging.debug("[pwnStart] plugin initialized")
    
    def on_loaded(self):
        logging.info("[pwnStart] plugin loaded")
        self.running = True
        
        try: 
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
            
            # Disable fix_services
            if hasattr(self.options, 'NoGPSPrivacy') and self.options['NoGPSPrivacy']:
                logging.info("[pwnStart] Disabling NoGPSPrivacy")
                self.options['NoGPSPrivacy'] = False
            else:
                logging.info("[pwnStart] NoGPSPrivacy was already disabled or not found")
            
            # Enable probenpwn extensions
            if hasattr(self.options, 'probenpwn') and self.options['probenpwn']:
                logging.info("[pwnStart] Enabling probenpwn")
                self.options['probenpwn'] = True
            else:
                logging.info("[pwnStart] probenpwn was already disabled or not found")
                
        except Exception as e:
            logging.error(f"[pwnStart] Error with extensions: {e}")
            
        logging.info("[pwnStart] Configuration complete!")
    
    def on_unload(self, ui):
        logging.info("[pwnStart] plugin unloaded")
        self.running = False
    
    def on_webhook(self, path, request):
        # Optional: add a webhook to check status or toggle settings
        return {'enabled': self.running}
