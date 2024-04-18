"""A entity class for mobile_app."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ICON, CONF_NAME, CONF_UNIQUE_ID, STATE_UNAVAILABLE
from homeassistant.core import State, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    ATTR_SENSOR_ATTRIBUTES,
    ATTR_SENSOR_DEVICE_CLASS,
    ATTR_SENSOR_DISABLED,
    ATTR_SENSOR_ENTITY_CATEGORY,
    ATTR_SENSOR_ICON,
    ATTR_SENSOR_STATE,
    ATTR_SENSOR_STATE_CLASS,
    SIGNAL_SENSOR_UPDATE,
)
from .helpers import device_info


class MobileAppEntity(RestoreEntity):
    """Representation of an mobile app entity."""

    _attr_should_poll = False

    def __init__(self, config: dict, entry: ConfigEntry) -> None:
        """Initialize the entity."""
        self._config = config
        self._entry = entry
        self._registration = entry.data
        self._attr_unique_id = config[CONF_UNIQUE_ID]
        self._attr_entity_registry_enabled_default = not config.get(
            ATTR_SENSOR_DISABLED
        )
        self._attr_name = config[CONF_NAME]
        self._async_update_attr_from_config()

    @callback
    def _async_update_attr_from_config(self) -> None:
        """Update the entity from the config."""
        config = self._config
        self._attr_device_class = config.get(ATTR_SENSOR_DEVICE_CLASS)
        self._attr_state_class = config.get(ATTR_SENSOR_STATE_CLASS)
        self._attr_extra_state_attributes = config[ATTR_SENSOR_ATTRIBUTES]
        self._attr_icon = config[ATTR_SENSOR_ICON]
        self._attr_entity_category = config.get(ATTR_SENSOR_ENTITY_CATEGORY)
        self._attr_available = config.get(ATTR_SENSOR_STATE) != STATE_UNAVAILABLE

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_SENSOR_UPDATE}-{self._attr_unique_id}",
                self._handle_update,
            )
        )

        if (state := await self.async_get_last_state()) is None:
            return

        await self.async_restore_last_state(state)

    async def async_restore_last_state(self, last_state: State) -> None:
        """Restore previous state."""
        config = self._config
        config[ATTR_SENSOR_STATE] = last_state.state
        config[ATTR_SENSOR_ATTRIBUTES] = {
            **last_state.attributes,
            **self._config[ATTR_SENSOR_ATTRIBUTES],
        }
        if ATTR_ICON in last_state.attributes:
            config[ATTR_SENSOR_ICON] = last_state.attributes[ATTR_ICON]

    @property
    def device_info(self):
        """Return device registry information for this entity."""
        return device_info(self._registration)

    @callback
    def _handle_update(self, data: dict[str, Any]) -> None:
        """Handle async event updates."""
        self._config.update(data)
        self._async_update_attr_from_config()
        self.async_write_ha_state()
