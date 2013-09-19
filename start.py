from app.HomeAssistant import HomeAssistant

from app.observer.TomatoDeviceScanner import TomatoDeviceScanner

ha = HomeAssistant()

ha.setup_device_tracker(TomatoDeviceScanner(ha.get_config()))
ha.setup_hue_trigger()

ha.start()
