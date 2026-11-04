"""Number entities for the NexBlue integration."""

from typing import override

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from nexblue_api import NexBlueError

from .const import ACTIVE_CHARGING_STATES, DOMAIN
from .coordinator import NexBlueConfigEntry, NexBlueDataUpdateCoordinator

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NexBlueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NexBlue numbers for every discovered charger."""
    coordinator = entry.runtime_data
    async_add_entities(
        NexBlueDynamicCurrentLimitNumber(coordinator, serial_number)
        for serial_number in coordinator.data
    )


class NexBlueDynamicCurrentLimitNumber(
    CoordinatorEntity[NexBlueDataUpdateCoordinator], NumberEntity
):
    """Control the dynamic current limit for a charging session."""

    entity_description = NumberEntityDescription(
        key="dynamic_current_limit",
        translation_key="dynamic_current_limit",
        device_class=NumberDeviceClass.CURRENT,
        entity_category=EntityCategory.CONFIG,
    )
    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX
    _attr_native_max_value = 32
    _attr_native_min_value = 6
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE

    def __init__(
        self,
        coordinator: NexBlueDataUpdateCoordinator,
        serial_number: str,
    ) -> None:
        """Initialize the dynamic current limit number."""
        super().__init__(coordinator)
        self._serial_number = serial_number
        self._attr_unique_id = f"{serial_number}_dynamic_current_limit"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            manufacturer="NexBlue",
            name=serial_number,
            serial_number=serial_number,
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether dynamic current limit is supported and available."""
        status = self.coordinator.data.get(self._serial_number)
        return (
            super().available
            and status is not None
            and status.dynamic_current_limit_a is not None
        )

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current dynamic limit."""
        status = self.coordinator.data.get(self._serial_number)
        if status is None or status.dynamic_current_limit_a is None:
            return None
        return round(status.dynamic_current_limit_a, 1)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the dynamic current limit."""
        status = self.coordinator.data.get(self._serial_number)
        if status is None or status.charging_state not in ACTIVE_CHARGING_STATES:
            raise HomeAssistantError(
                "Current limit can only be changed during an active charging session"
            )

        try:
            await self.coordinator.client.async_set_dynamic_current_limit(
                self._serial_number, value
            )
        except NexBlueError as err:
            raise HomeAssistantError(str(err)) from err

        await self.coordinator.async_request_refresh()
