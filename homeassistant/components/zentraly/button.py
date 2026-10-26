"""Diagnostic actions for Zentraly devices."""

from typing import override

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .actions import translate_action_errors
from .models import ZentralyConfigEntry, ZentralyData

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZentralyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the metadata refresh button when the device supports versions."""
    if entry.runtime_data.device.supports_device_info:
        async_add_entities([ZentralyRefreshDeviceInfoButton(entry.runtime_data)])


class ZentralyRefreshDeviceInfoButton(ButtonEntity):
    """Refresh hardware and firmware versions in the device registry."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "refresh_device_info"

    def __init__(self, data: ZentralyData) -> None:
        """Initialize the diagnostic button."""
        self._data = data
        self._attr_unique_id = f"{data.device.device_id}_refresh_device_info"
        self._attr_device_info = data.device.device_info

    @property
    @override
    def available(self) -> bool:
        """Require an available connection for a manual refresh."""
        return (
            super().available
            and self._data.device.available
            and self._data.device.connected
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Track device availability."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._data.device.add_state_listener(self.async_write_ha_state)
        )
        self.async_on_remove(
            self._data.device.add_connection_state_listener(
                self._handle_connection_state
            )
        )

    def _handle_connection_state(self, connected: bool) -> None:
        """Publish connection availability."""
        self.async_write_ha_state()

    @override
    @translate_action_errors
    async def async_press(self) -> None:
        """Read versions and update the existing device registry entry."""
        await self._data.async_refresh_device_info()
