"""Sensor for Livebox router."""
import logging

from homeassistant.components.switch import SwitchDevice

from .const import DOMAIN, ID_BOX, SESSION_SYSBUS, TEMPLATE_SENSOR

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensors."""
    box_id = hass.data[DOMAIN][ID_BOX]
    session = hass.data[DOMAIN][SESSION_SYSBUS]
    async_add_entities([WifiSwitch(session, box_id)], True)


class WifiSwitch(SwitchDevice):
    """Representation of a livebox sensor."""

    def __init__(self, session, box_id):
        """Initialize the sensor."""
        self._session = session
        self._box_id = box_id
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Wifi switch"

    @property
    def unique_id(self):
        """Return unique_id."""
        return f"{self._box_id}_wifi"

    @property
    def device_info(self):
        """Return the device info."""

        return {
            "name": self.name,
            "identifiers": {(DOMAIN, self.unique_id)},
            "manufacturer": TEMPLATE_SENSOR,
            "via_device": (DOMAIN, self._box_id),
        }

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        parameters = {"parameters": {"Enable": "true", "Status": "true"}}
        await self._session.wifi.set_wifi(parameters)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        parameters = {"parameters": {"Enable": "false", "Status": "false"}}
        await self._session.wifi.set_wifi(parameters)

    async def async_update(self):
        """Return update entry."""
        _state = await self._session.wifi.get_wifi()
        self._state = _state["status"]["Enable"] == "true"
