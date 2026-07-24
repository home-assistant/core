"""Support for MELCloud device selects."""

from typing import override

from pymelcloud import DEVICE_TYPE_ATW
from pymelcloud.atw_device import Zone

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MelCloudConfigEntry, MelCloudDeviceUpdateCoordinator
from .entity import MelCloudEntity


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: MelCloudConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MELCloud selects based on config_entry."""
    coordinators = entry.runtime_data
    async_add_entities(
        AtwZoneOperationModeSelect(coordinator, zone)
        for coordinator in coordinators.get(DEVICE_TYPE_ATW, [])
        for zone in coordinator.device.zones
    )


class AtwZoneOperationModeSelect(MelCloudEntity, SelectEntity):
    """Select for the operation mode of an Air-to-Water zone."""

    _attr_translation_key = "operation_mode"

    def __init__(
        self,
        coordinator: MelCloudDeviceUpdateCoordinator,
        zone: Zone,
    ) -> None:
        """Initialize the operation mode select."""
        super().__init__(coordinator)
        self._zone = zone
        self._attr_unique_id = (
            f"{coordinator.device.serial}-{zone.zone_index}-operation_mode"
        )
        self._attr_device_info = coordinator.zone_device_info(zone)
        self._attr_options = zone.operation_modes

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current operation mode."""
        option = self._zone.operation_mode
        return option if option in self._attr_options else None

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the operation mode."""
        await self._zone.set_operation_mode(option)
        await self.coordinator.async_request_refresh()
