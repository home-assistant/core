"""Button platform for the Daikin Onecta integration."""

import logging
from typing import override

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import OnectaDataUpdateCoordinator
from .device import DaikinOnectaDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
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


class DaikinRefreshButton(CoordinatorEntity, ButtonEntity):
    """Button to request an immediate device data update."""

    def __init__(
        self,
        device: DaikinOnectaDevice,
        config_entry: ConfigEntry,
        coordinator: OnectaDataUpdateCoordinator,
    ) -> None:
        """Initialize a refresh button for a device."""
        super().__init__(coordinator)
        self._device = device
        self._attr_unique_id = f"{self._device.id}_refresh"
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_icon = "mdi:refresh"
        self._attr_name = "Refresh"
        self._attr_device_info = self._device.device_info()
        self._device.fill_gateway_device_info(self._attr_device_info)
        self._attr_has_entity_name = True
        self._config_entry = config_entry

        _LOGGER.info("Device '%s' has refresh button", self._device.name)

    @property
    @override
    def available(self) -> bool:
        """Return whether the source device is available."""
        return self._device.available

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    @override
    async def async_press(self) -> None:
        """Request an immediate coordinator refresh."""
        await self.coordinator.async_refresh()
