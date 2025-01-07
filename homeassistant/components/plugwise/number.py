"""Number platform for Plugwise integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PlugwiseConfigEntry
from .const import NumberType
from .coordinator import PlugwiseDataUpdateCoordinator
from .entity import PlugwiseEntity
from .util import plugwise_command

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PlugwiseNumberEntityDescription(NumberEntityDescription):
    """Class describing Plugwise Number entities."""

    key: NumberType


NUMBER_TYPES = (
    PlugwiseNumberEntityDescription(
        key="maximum_boiler_temperature",
        translation_key="maximum_boiler_temperature",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    PlugwiseNumberEntityDescription(
        key="max_dhw_temperature",
        translation_key="max_dhw_temperature",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    PlugwiseNumberEntityDescription(
        key="temperature_offset",
        translation_key="temperature_offset",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlugwiseConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Plugwise number platform."""
    coordinator = entry.runtime_data

    @callback
    def _add_entities() -> None:
        """Add Entities."""
        if not coordinator.new_devices:
            return

        async_add_entities(
            PlugwiseNumberEntity(coordinator, device_id, description)
            for device_id in coordinator.new_devices
            for description in NUMBER_TYPES
            if description.key in coordinator.data.devices[device_id]
        )

    _add_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_entities))


class PlugwiseNumberEntity(PlugwiseEntity, NumberEntity):
    """Representation of a Plugwise number."""

    entity_description: PlugwiseNumberEntityDescription

    def __init__(
        self,
        coordinator: PlugwiseDataUpdateCoordinator,
        device_id: str,
        description: PlugwiseNumberEntityDescription,
    ) -> None:
        """Initiate Plugwise Number."""
        super().__init__(coordinator, device_id)
        self._attr_mode = NumberMode.BOX
        self._attr_native_max_value = self.device[description.key]["upper_bound"]
        self._attr_native_min_value = self.device[description.key]["lower_bound"]
        self._attr_unique_id = f"{device_id}-{description.key}"
        self.device_id = device_id
        self.entity_description = description

        native_step = self.device[description.key]["resolution"]
        if description.key != "temperature_offset":
            native_step = max(native_step, 0.5)
        self._attr_native_step = native_step

    @property
    def native_value(self) -> float:
        """Return the present setpoint value."""
        return self.device[self.entity_description.key]["setpoint"]

    @plugwise_command
    async def async_set_native_value(self, value: float) -> None:
        """Change to the new setpoint value."""
        await self.coordinator.api.set_number(
            self.device_id, self.entity_description.key, value
        )
