"""Support for wired switches attached to a Konnected device."""
import logging

from homeassistant.const import (
    ATTR_STATE,
    CONF_DEVICES,
    CONF_NAME,
    CONF_SWITCHES,
    CONF_ZONE,
)
from homeassistant.helpers.entity import ToggleEntity

from .const import (
    CONF_ACTIVATION,
    CONF_MOMENTARY,
    CONF_PAUSE,
    CONF_REPEAT,
    DOMAIN as KONNECTED_DOMAIN,
    STATE_HIGH,
    STATE_LOW,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up switches attached to a Konnected device from a config entry."""
    data = hass.data[KONNECTED_DOMAIN]
    device_id = config_entry.data["id"]
    switches = [
        KonnectedSwitch(device_id, zone_data.get(CONF_ZONE), zone_data)
        for zone_data in data[CONF_DEVICES][device_id][CONF_SWITCHES]
    ]
    async_add_entities(switches)


class KonnectedSwitch(ToggleEntity):
    """Representation of a Konnected switch."""

    def __init__(self, device_id, zone_num, data):
        """Initialize the Konnected switch."""
        self._data = data
        self._device_id = device_id
        self._zone_num = zone_num
        self._activation = self._data.get(CONF_ACTIVATION, STATE_HIGH)
        self._momentary = self._data.get(CONF_MOMENTARY)
        self._pause = self._data.get(CONF_PAUSE)
        self._repeat = self._data.get(CONF_REPEAT)
        self._state = self._boolean_state(self._data.get(ATTR_STATE))
        self._name = self._data.get(CONF_NAME)
        self._unique_id = (
            f"{device_id}-{self._zone_num}-{self._momentary}-"
            f"{self._pause}-{self._repeat}"
        )

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return the status of the sensor."""
        return self._state

    @property
    def panel(self):
        """Return the Konnected HTTP client."""
        device_data = self.hass.data[KONNECTED_DOMAIN][CONF_DEVICES][self._device_id]
        return device_data.get("panel")

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(KONNECTED_DOMAIN, self._device_id)},
        }

    @property
    def available(self):
        """Return whether the panel is available."""
        return self.panel.available

    async def async_turn_on(self, **kwargs):
        """Send a command to turn on the switch."""
        resp = await self.panel.update_switch(
            self._zone_num,
            int(self._activation == STATE_HIGH),
            self._momentary,
            self._repeat,
            self._pause,
        )

        if resp.get(ATTR_STATE) is not None:
            self._set_state(True)

            if self._momentary and resp.get(ATTR_STATE) != -1:
                # Immediately set the state back off for momentary switches
                self._set_state(False)

    async def async_turn_off(self, **kwargs):
        """Send a command to turn off the switch."""
        resp = await self.panel.update_switch(
            self._zone_num, int(self._activation == STATE_LOW)
        )

        if resp.get(ATTR_STATE) is not None:
            self._set_state(self._boolean_state(resp.get(ATTR_STATE)))

    def _boolean_state(self, int_state):
        if int_state is None:
            return False
        if int_state == 0:
            return self._activation == STATE_LOW
        if int_state == 1:
            return self._activation == STATE_HIGH

    def _set_state(self, state):
        self._state = state
        self.async_write_ha_state()
        _LOGGER.debug(
            "Setting status of %s actuator zone %s to %s",
            self._device_id,
            self.name,
            state,
        )

    async def async_added_to_hass(self):
        """Store entity_id."""
        self._data["entity_id"] = self.entity_id
