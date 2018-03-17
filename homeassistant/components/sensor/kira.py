"""
KIRA interface to receive UDP packets from an IR-IP bridge.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.kira/
"""
import logging

from homeassistant.const import CONF_DEVICE, CONF_NAME, STATE_UNKNOWN
from homeassistant.helpers.entity import Entity

DOMAIN = 'kira'

_LOGGER = logging.getLogger(__name__)

ICON = 'mdi:remote'

CONF_SENSOR = 'sensor'


# pylint: disable=unused-argument, too-many-function-args
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up a Kira sensor."""
    if discovery_info is not None:
        name = discovery_info.get(CONF_NAME)
        device = discovery_info.get(CONF_DEVICE)
        kira = hass.data[DOMAIN][CONF_SENSOR][name]

        add_devices([KiraReceiver(device, kira)])


class KiraReceiver(Entity):
    """Implementation of a Kira Receiver."""

    def __init__(self, name, kira):
        """Initialize the sensor."""
        self._name = name
        self._state = None
        self._device = STATE_UNKNOWN

        kira.registerCallback(self._update_callback)

    def _update_callback(self, code):
        code_name, device = code
        _LOGGER.debug("Kira Code: %s", code_name)
        self._state = code_name
        self._device = device
        self.schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the receiver."""
        return self._name

    @property
    def icon(self):
        """Return icon."""
        return ICON

    @property
    def state(self):
        """Return the state of the receiver."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return {CONF_DEVICE: self._device}

    @property
    def should_poll(self) -> bool:
        """Entity should not be polled."""
        return False

    @property
    def force_update(self) -> bool:
        """Kira should force updates. Repeated states have meaning."""
        return True
