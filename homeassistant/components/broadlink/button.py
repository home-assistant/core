"""Support for Broadlink buttons."""

from typing import override

from broadlink_async.exceptions import BroadlinkException

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import BROADLINK_DATA, DOMAIN
from .device import BroadlinkDevice
from .entity import BroadlinkEntity
from .updater import BroadlinkThermostatUpdateManager


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Broadlink buttons."""
    device = hass.data[BROADLINK_DATA].devices[config_entry.entry_id]
    async_add_entities([BroadlinkSyncTimeButton(device)])


class BroadlinkSyncTimeButton(BroadlinkEntity, ButtonEntity):
    """A button that sets the thermostat clock to the Home Assistant local time."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "sync_time"

    def __init__(self, device: BroadlinkDevice) -> None:
        """Initialize the button."""
        super().__init__(device)
        self._attr_unique_id = f"{device.unique_id}-sync_time"

    @override
    async def async_press(self) -> None:
        """Set the thermostat clock."""
        update_manager = self._device.update_manager
        assert isinstance(update_manager, BroadlinkThermostatUpdateManager)
        try:
            await update_manager.async_sync_time()
        except (BroadlinkException, OSError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="sync_time_failed",
                translation_placeholders={"error": str(err)},
            ) from err
