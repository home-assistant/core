"""Support for wired switches attached to a Konnected device."""
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_STATE,
    CONF_DEVICES,
    CONF_NAME,
    CONF_REPEAT,
    CONF_SWITCHES,
    CONF_ZONE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ACTIVATION,
    CONF_MOMENTARY,
    CONF_PAUSE,
    DOMAIN as KONNECTED_DOMAIN,
    STATE_HIGH,
    STATE_LOW,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches attached to a Konnected device from a config entry."""
    data = hass.data[KONNECTED_DOMAIN]
    device_id = config_entry.data["id"]
    switches = [
        KonnectedSwitch(device_id, zone_data.get(CONF_ZONE), zone_data)
        for zone_data in data[CONF_DEVICES][device_id][CONF_SWITCHES]
    ]
    async_add_entities(switches)


class KonnectedSwitch(SwitchEntity):
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
        self._attr_is_on = self._boolean_state(self._data.get(ATTR_STATE))
        self._attr_name = self._data.get(CONF_NAME)
        self._attr_unique_id = (
            f"{device_id}-{self._zone_num}-{self._momentary}-"
            f"{self._pause}-{self._repeat}"
        )
        self._attr_device_info = DeviceInfo(identifiers={(KONNECTED_DOMAIN, device_id)})

    @property
    def panel(self):
        """Return the Konnected HTTP client."""
        device_data = self.hass.data[KONNECTED_DOMAIN][CONF_DEVICES][self._device_id]
        return device_data.get("panel")

    @property
    def available(self) -> bool:
        """Return whether the panel is available."""
        return self.panel.available

    async def async_turn_on(self, **kwargs: Any) -> None:
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

    async def async_turn_off(self, **kwargs: Any) -> None:
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
        self._attr_is_on = state
        self.async_write_ha_state()
        _LOGGER.debug(
            "Setting status of %s actuator zone %s to %s",
            self._device_id,
            self.name,
            state,
        )

    @callback
    def async_set_state(self, state):
        """Update the switch state."""
        self._set_state(state)

    async def async_added_to_hass(self) -> None:
        """Store entity_id and register state change callback."""
        self._data["entity_id"] = self.entity_id
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"konnected.{self.entity_id}.update", self.async_set_state
            )
        )
