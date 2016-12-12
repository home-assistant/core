"""
Support for HDMI CEC devices as switches.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/hdmi_cec/
"""
import asyncio
import logging

from homeassistant.components.hdmi_cec import CecDevice, CEC_CLIENT, ATTR_NEW, DEVICE_PRESENCE
from homeassistant.components.switch import SwitchDevice, DOMAIN
from homeassistant.const import STATE_OFF, STATE_STANDBY, STATE_ON

DEPENDENCIES = ['hdmi_cec']

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + '.{}'


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Find and return HDMI devices as switches."""
    if ATTR_NEW in discovery_info:
        _LOGGER.info("Setting up devices %s", discovery_info[ATTR_NEW])
        devices = [CecSwitch(hass, CEC_CLIENT, device) for device in
                   filter(lambda x: x not in DEVICE_PRESENCE or not DEVICE_PRESENCE[x], discovery_info[ATTR_NEW])]
        yield from async_add_devices(devices)
        for d in devices:
            yield from d.async_update()


class CecSwitch(CecDevice, SwitchDevice):
    """Representation of a HDMI device as a Switch."""

    def __init__(self, hass, cec_client, logical):
        """Initialize the HDMI device."""
        self._state = False
        CecDevice.__init__(self, hass, cec_client, logical)
        self.entity_id = "%s.%s_%s" % (DOMAIN, 'hdmi', hex(self._logical_address)[2:])

    def turn_on(self, **kwargs) -> None:
        """Turn device on."""
        self.cec_client.lib_cec.PowerOnDevices(self._logical_address)
        self._state = STATE_ON
        self.async_update()
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs) -> None:
        """Turn device off."""
        self.cec_client.lib_cec.StandbyDevices(self._logical_address)
        self._state = STATE_STANDBY
        self.async_update()
        self.schedule_update_ha_state()

    @property
    def is_standby(self):
        """Return true if device is in standby."""
        return self._state == STATE_OFF or self._state == STATE_STANDBY
