"""Support for IntelliDwell Sprinkler Controller numbers."""

import logging
from typing import override

from pyintellidwell import IntelliDwellConnectionError

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IntelliDwellConfigEntry
from .const import DOMAIN
from .coordinator import IntelliDwellCoordinator

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: IntelliDwellConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the number platform."""
    coordinator: IntelliDwellCoordinator = config_entry.runtime_data

    async_add_entities([IntelliDwellRainDelayNumber(coordinator, config_entry)])


class IntelliDwellRainDelayNumber(
    CoordinatorEntity[IntelliDwellCoordinator], NumberEntity
):
    """Representation of an IntelliDwell Rain Delay number control."""

    _attr_has_entity_name = True
    _attr_device_class = NumberDeviceClass.DURATION
    _attr_icon = "mdi:weather-pouring"
    _attr_translation_key = "rain_delay"
    _attr_native_min_value = 0
    _attr_native_max_value = 5
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "d"
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: IntelliDwellCoordinator,
        config_entry: IntelliDwellConfigEntry,
    ) -> None:
        """Initialize the rain delay entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{config_entry.entry_id}_rain_delay"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name="IntelliDwell Sprinkler Controller",
            manufacturer="IntelliDwell",
            model="Sprinkler Controller V2",
            configuration_url=f"http://{coordinator.client.host}",
        )

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current rain delay remaining days."""
        return float(self.coordinator.data.get("rain_delay", 0))

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set rain delay days (0 to 5)."""
        if not value.is_integer():
            raise ServiceValidationError(
                "Rain delay value must be a whole number of days"
            )
        days = int(value)
        try:
            await self.coordinator.client.set_rain_delay(days)
        except IntelliDwellConnectionError as err:
            raise HomeAssistantError(
                f"Error setting rain delay to {days} days: {err}"
            ) from err

        await self.coordinator.async_request_refresh()
