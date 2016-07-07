"""
Support for Autohub.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/autohub/
"""
import logging

from homeassistant.components.discovery import SERVICE_AUTOHUB


from homeassistant.const import (CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME, 
EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers import validate_config, discovery

DOMAIN = "autohub"
REQUIREMENTS = ['pyautohub==0.1.0']
AUTOHUB = None
DISCOVER_LIGHTS = "autohub.light"


# Mapping from Wemo model_name to service.
AUTOHUB_MODEL_DISPATCH = {
}

AUTOHUB_SERVICE_DISPATCH = {
    DISCOVER_LIGHTS: 'light',
}

AUTOHUBWS = None

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """Setup Autohub Hub component.
    This will automatically import associated lights.
    """
    if not validate_config(
            config,
            {DOMAIN: [CONF_USERNAME, CONF_PASSWORD, CONF_API_KEY]},
            _LOGGER):
        return False

    import pyautohub

    global AUTOHUBWS
    AUTOHUBWS = pyautohub.AutohubWS()

    # callback handler
    def OnDeviceAdded(device):
        config_autohub = config.get("autohub")
        kDevices = config_autohub.get("devices", {})
        if device.device_address_ in kDevices:
          device.device_name_ = kDevices[device.device_address_].get("name", device.device_name_)
        discovery_info = (device.device_address_, device.device_name_)
        discovery.discover(hass, SERVICE_AUTOHUB, discovery_info)

    # register callback handler with pyautohub
    AUTOHUBWS.on_device_added(OnDeviceAdded)
	
    def autohub_stop(event):
      _LOGGER.info("Shutting down Authub sockets")
      AUTOHUBWS.stop()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, autohub_stop)

    def discovery_dispatch(service, device):
        """Dispatcher for autohub discovery events."""
        # name, model, location, mac
        device_address, device_name = device
		
        service = DISCOVER_LIGHTS
        component = AUTOHUB_SERVICE_DISPATCH.get(service)
		
        discovery.load_platform(hass, component, DOMAIN, device, config)

        discovery.discover(hass, service, device, component, config)

    discovery.listen(hass, SERVICE_AUTOHUB, discovery_dispatch)
    AUTOHUBWS.start()
    # AUTOHUBWS.getDeviceList()

    return True

