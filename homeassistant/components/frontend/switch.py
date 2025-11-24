"""Switch platform for frontend integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .storage import async_system_store

DOMAIN = "frontend"
STORAGE_KEY_WINTER_MODE = "winter_mode"
STORAGE_SUBKEY_ENABLED = "enabled"


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the frontend switch platform."""
    async_add_entities([FrontendWinterModeSwitch(hass)])


class FrontendWinterModeSwitch(SwitchEntity, RestoreEntity):
    """Switch to enable winter mode in the frontend."""

    _attr_has_entity_name = False
    _attr_name = "Winter mode"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "winter_mode"
    _attr_unique_id = "frontend_winter_mode"
    _attr_icon = "mdi:snowflake"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the winter mode switch."""
        self.hass = hass

    async def async_added_to_hass(self) -> None:
        """Restore state when added to hass."""
        await super().async_added_to_hass()

        # Try to restore from system storage first
        store = await async_system_store(self.hass)
        winter_mode_data = store.data.get(STORAGE_KEY_WINTER_MODE)

        if (
            isinstance(winter_mode_data, dict)
            and STORAGE_SUBKEY_ENABLED in winter_mode_data
        ):
            self._attr_is_on = bool(winter_mode_data[STORAGE_SUBKEY_ENABLED])
        else:
            # Fall back to restore entity state
            last_state = await self.async_get_last_state()
            self._attr_is_on = last_state is not None and last_state.state == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on winter mode."""
        self._attr_is_on = True
        self.async_write_ha_state()

        # Save to system storage
        store = await async_system_store(self.hass)
        await store.async_set_item(
            STORAGE_KEY_WINTER_MODE, {STORAGE_SUBKEY_ENABLED: True}
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off winter mode."""
        self._attr_is_on = False
        self.async_write_ha_state()

        # Save to system storage
        store = await async_system_store(self.hass)
        await store.async_set_item(
            STORAGE_KEY_WINTER_MODE, {STORAGE_SUBKEY_ENABLED: False}
        )
