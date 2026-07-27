"""Support for MELCloud device numbers."""

from typing import override

from pymelcloud import DEVICE_TYPE_ATW
from pymelcloud.atw_device import (
    ZONE_OPERATION_MODE_COOL_FLOW,
    ZONE_OPERATION_MODE_HEAT_FLOW,
    Zone,
)

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MelCloudConfigEntry, MelCloudDeviceUpdateCoordinator
from .entity import MelCloudEntity

# The flow temperature only applies while the zone is controlled by flow
# temperature; the number is unavailable in the other control methods.
FLOW_MODES = {ZONE_OPERATION_MODE_HEAT_FLOW, ZONE_OPERATION_MODE_COOL_FLOW}


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: MelCloudConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MELCloud numbers based on config_entry."""
    coordinators = entry.runtime_data
    async_add_entities(
        AtwZoneFlowTemperatureNumber(coordinator, zone)
        for coordinator in coordinators.get(DEVICE_TYPE_ATW, [])
        for zone in coordinator.device.zones
    )


class AtwZoneFlowTemperatureNumber(MelCloudEntity, NumberEntity):
    """Number for the target flow temperature of an Air-to-Water zone."""

    _attr_translation_key = "flow_temperature"
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: MelCloudDeviceUpdateCoordinator,
        zone: Zone,
    ) -> None:
        """Initialize the flow temperature number."""
        super().__init__(coordinator)
        self._zone = zone
        self._attr_unique_id = (
            f"{coordinator.device.serial}-{zone.zone_index}-flow_temperature"
        )
        self._attr_device_info = coordinator.zone_device_info(zone)
        self._attr_native_step = coordinator.device.temperature_increment

    @property
    @override
    def available(self) -> bool:
        """Return True only while the zone is controlled by flow temperature."""
        return super().available and self._zone.operation_mode in FLOW_MODES

    @property
    @override
    def native_min_value(self) -> float:
        """Return the minimum settable flow temperature."""
        if self._zone.operation_mode == ZONE_OPERATION_MODE_COOL_FLOW:
            return 5
        return 25

    @property
    @override
    def native_max_value(self) -> float:
        """Return the maximum settable flow temperature."""
        if self._zone.operation_mode == ZONE_OPERATION_MODE_COOL_FLOW:
            return 25
        return 60

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current target flow temperature."""
        return self._zone.target_flow_temperature

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set a new target flow temperature."""
        await self._zone.set_target_flow_temperature(value)
        await self.coordinator.async_request_refresh()
