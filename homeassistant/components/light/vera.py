"""
homeassistant.components.light.vera
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Vera lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.vera/
"""
import logging

from requests.exceptions import RequestException
from homeassistant.components.switch.vera import VeraSwitch

from homeassistant.components.light import ATTR_BRIGHTNESS

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, STATE_ON

REQUIREMENTS = ['pyvera==0.2.7']

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return Vera lights. """
    import pyvera as veraApi

    base_url = config.get('vera_controller_url')
    if not base_url:
        _LOGGER.error(
            "The required parameter 'vera_controller_url'"
            " was not found in config"
        )
        return False

    device_data = config.get('device_data', {})

    vera_controller, created = veraApi.init_controller(base_url)

    if created:
        def stop_subscription(event):
            """ Shutdown Vera subscriptions and subscription thread on exit"""
            _LOGGER.info("Shutting down subscriptions.")
            vera_controller.stop()

        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_subscription)

    devices = []
    try:
        devices = vera_controller.get_devices([
            'Switch',
            'On/Off Switch',
            'Dimmable Switch'])
    except RequestException:
        # There was a network related error connecting to the vera controller
        _LOGGER.exception("Error communicating with Vera API")
        return False

    lights = []
    for device in devices:
        extra_data = device_data.get(device.device_id, {})
        exclude = extra_data.get('exclude', False)

        if exclude is not True:
            lights.append(VeraLight(device, vera_controller, extra_data))

    add_devices_callback(lights)


class VeraLight(VeraSwitch):
    """ Represents a Vera Light, including dimmable. """

    @property
    def state_attributes(self):
        attr = super().state_attributes or {}

        if self.vera_device.is_dimmable:
            attr[ATTR_BRIGHTNESS] = self.vera_device.get_brightness()

        return attr

    def turn_on(self, **kwargs):
        if ATTR_BRIGHTNESS in kwargs and self.vera_device.is_dimmable:
            self.vera_device.set_brightness(kwargs[ATTR_BRIGHTNESS])
        else:
            self.vera_device.switch_on()

        self._state = STATE_ON
        self.update_ha_state(True)
