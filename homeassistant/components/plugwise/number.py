"""Number platform for Plugwise integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from plugwise import Smile

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, NumberType
from .coordinator import PlugwiseDataUpdateCoordinator
from .entity import PlugwiseEntity


@dataclass(frozen=True, kw_only=True)
class PlugwiseNumberEntityDescription(NumberEntityDescription):
    """Class describing Plugwise Number entities."""

    command: Callable[[Smile, str, str, float], Awaitable[None]]
    key: NumberType


NUMBER_TYPES = (
    PlugwiseNumberEntityDescription(
        key="maximum_boiler_temperature",
        translation_key="maximum_boiler_temperature",
        command=lambda api, number, dev_id, value: api.set_number_setpoint(
            number, dev_id, value
        ),
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    PlugwiseNumberEntityDescription(
        key="max_dhw_temperature",
        translation_key="max_dhw_temperature",
        command=lambda api, number, dev_id, value: api.set_number_setpoint(
            number, dev_id, value
        ),
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    PlugwiseNumberEntityDescription(
        key="temperature_offset",
        translation_key="temperature_offset",
        command=lambda api, number, dev_id, value: api.set_temperature_offset(
            number, dev_id, value
        ),
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Plugwise number platform."""

    coordinator: PlugwiseDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    async_add_entities(
        PlugwiseNumberEntity(coordinator, device_id, description)
        for device_id, device in coordinator.data.devices.items()
        for description in NUMBER_TYPES
        if description.key in device
    )


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
        self.device_id = device_id
        self.entity_description = description
        self._attr_unique_id = f"{device_id}-{description.key}"
        self._attr_mode = NumberMode.BOX
        self._attr_native_max_value = self.device[description.key]["upper_bound"]
        self._attr_native_min_value = self.device[description.key]["lower_bound"]

        native_step = self.device[description.key]["resolution"]
        if description.key != "temperature_offset":
            native_step = max(native_step, 0.5)
        self._attr_native_step = native_step

    @property
    def native_value(self) -> float:
        """Return the present setpoint value."""
        return self.device[self.entity_description.key]["setpoint"]

    async def async_set_native_value(self, value: float) -> None:
        """Change to the new setpoint value."""
        await self.entity_description.command(
            self.coordinator.api, self.entity_description.key, self.device_id, value
        )
        await self.coordinator.async_request_refresh()
