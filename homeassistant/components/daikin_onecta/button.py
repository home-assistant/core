"""Button platform for the Daikin Onecta integration."""

import logging
from typing import override

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DaikinOnectaConfigEntry, OnectaDataUpdateCoordinator
from .device import DaikinOnectaDevice
from .entity import DaikinEntity
from .entity_descriptions import BUTTON_DESCRIPTIONS

PARALLEL_UPDATES = 1

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DaikinOnectaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up refresh buttons for configured Daikin devices."""
    coordinator: OnectaDataUpdateCoordinator = config_entry.runtime_data

    entities = [
        DaikinRefreshButton(device, config_entry, coordinator)
        for device in (coordinator.data or {}).values()
    ]

    if entities:
        async_add_entities(entities)


class DaikinRefreshButton(DaikinEntity, ButtonEntity):
    """Button to request an immediate device data update."""

    def __init__(
        self,
        device: DaikinOnectaDevice,
        config_entry: DaikinOnectaConfigEntry,
        coordinator: OnectaDataUpdateCoordinator,
    ) -> None:
        """Initialize a refresh button for a device."""
        super().__init__(device, coordinator)
        self._attr_unique_id = f"{self._device.id}_refresh"
        self.entity_description = BUTTON_DESCRIPTIONS["refresh"]
        self._config_entry = config_entry

        _LOGGER.info("Device '%s' has refresh button", self._device.name)

    @property
    @override
    def available(self) -> bool:
        """Return whether the device can be refreshed."""
        return self._device.available

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    @override
    async def async_press(self) -> None:
        """Request an immediate coordinator refresh."""
        await self.coordinator.async_refresh()
        if not self.coordinator.last_update_success:
            self._raise_command_failed("refresh_failed")
