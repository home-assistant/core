"""Number platform for Plugwise integration."""

from dataclasses import dataclass
from typing import override

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import NumberType
from .coordinator import PlugwiseConfigEntry, PlugwiseDataUpdateCoordinator
from .entity import PlugwiseEntity
from .util import deprecate_entity, plugwise_command

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PlugwiseNumberEntityDescription(NumberEntityDescription):
    """Class describing Plugwise Number entities."""

    key: NumberType


NUMBER_TYPES = (
    PlugwiseNumberEntityDescription(
        key="boiler_temperature",
        translation_key="maximum_boiler_temperature",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    PlugwiseNumberEntityDescription(
        key="dhw_temperature",
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
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Plugwise number platform."""
    coordinator = entry.runtime_data
    entity_registry = er.async_get(hass)

    @callback
    def _add_entities() -> None:
        """Add Entities."""
        if not coordinator.new_devices:
            return

        entities = []
        for device_id in coordinator.new_devices:
            for description in NUMBER_TYPES:
                if description.key not in coordinator.data[device_id]:
                    continue
                if description.key == "dhw_temperature" and not deprecate_entity(
                    hass,
                    entity_registry,
                    async_on_unload=entry.async_on_unload,
                    platform_domain=Platform.NUMBER,
                    entity_unique_id=f"{device_id}-{description.translation_key}",
                    issue_id=f"deprecated_dhw_temperature_{device_id}",
                    translation_key="deprecated_dhw_temperature",
                ):
                    continue
                entities.append(
                    PlugwiseNumberEntity(coordinator, device_id, description)
                )

        async_add_entities(entities)

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
        self._attr_unique_id = f"{device_id}-{description.translation_key}"
        self.device_id = device_id
        self.entity_description = description

        native_step = self.device[description.key]["resolution"]
        if description.key != "temperature_offset":
            native_step = max(native_step, 0.5)
        self._attr_native_step = native_step

    @property
    @override
    def native_value(self) -> float:
        """Return the present setpoint value."""
        return self.device[self.entity_description.key]["setpoint"]

    @plugwise_command
    @override
    async def async_set_native_value(self, value: float) -> None:
        """Change to the new setpoint value."""
        await self.coordinator.api.set_number(
            self.device_id, self.entity_description.key, value
        )
