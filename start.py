from homeassistant.HomeAssistant import HomeAssistant

from homeassistant.actor.HueLightControl import HueLightControl
from homeassistant.observer.TomatoDeviceScanner import TomatoDeviceScanner

ha = HomeAssistant()

ha.setup_device_tracker(TomatoDeviceScanner(ha.get_config()))
ha.setup_light_trigger(HueLightControl(ha.get_config()))
ha.setup_http_interface()

ha.start()
