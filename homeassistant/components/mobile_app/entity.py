"""A entity class for mobile_app."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ICON, CONF_NAME, CONF_UNIQUE_ID, STATE_UNAVAILABLE
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    ATTR_SENSOR_ATTRIBUTES,
    ATTR_SENSOR_DEVICE_CLASS,
    ATTR_SENSOR_DISABLED,
    ATTR_SENSOR_ENTITY_CATEGORY,
    ATTR_SENSOR_ICON,
    ATTR_SENSOR_STATE,
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
        self._name = self._config[CONF_NAME]

    async def async_added_to_hass(self):
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

    async def async_restore_last_state(self, last_state):
        """Restore previous state."""
        self._config[ATTR_SENSOR_STATE] = last_state.state
        self._config[ATTR_SENSOR_ATTRIBUTES] = {
            **last_state.attributes,
            **self._config[ATTR_SENSOR_ATTRIBUTES],
        }
        if ATTR_ICON in last_state.attributes:
            self._config[ATTR_SENSOR_ICON] = last_state.attributes[ATTR_ICON]

    @property
    def name(self):
        """Return the name of the mobile app sensor."""
        return self._name

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if entity should be enabled by default."""
        return not self._config.get(ATTR_SENSOR_DISABLED)

    @property
    def device_class(self):
        """Return the device class."""
        return self._config.get(ATTR_SENSOR_DEVICE_CLASS)

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        return self._config[ATTR_SENSOR_ATTRIBUTES]

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._config[ATTR_SENSOR_ICON]

    @property
    def entity_category(self):
        """Return the entity category, if any."""
        return self._config.get(ATTR_SENSOR_ENTITY_CATEGORY)

    @property
    def device_info(self):
        """Return device registry information for this entity."""
        return device_info(self._registration)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._config.get(ATTR_SENSOR_STATE) != STATE_UNAVAILABLE

    @callback
    def _handle_update(self, data: dict[str, Any]) -> None:
        """Handle async event updates."""
        self._config.update(data)
        self.async_write_ha_state()
