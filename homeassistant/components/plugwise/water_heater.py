"""Plugwise water heater component for Home Assistant."""

from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.water_heater import (
    STATE_ECO,
    WaterHeaterEntity,
    WaterHeaterEntityDescription,
    WaterHeaterEntityFeature,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    STATE_OFF,
    STATE_ON,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    BOILER_TEMP,
    DHW_MODE,
    DHW_MODES,
    DHW_TEMP,
    LOWER_BOUND,
    UPPER_BOUND,
    WaterHeaterOptionsType,
    WaterHeaterType,
)
from .coordinator import PlugwiseConfigEntry, PlugwiseDataUpdateCoordinator
from .entity import PlugwiseEntity
from .util import plugwise_command

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PlugwiseWaterHeaterEntityDescription(WaterHeaterEntityDescription):
    """Class describing Plugwise WaterHeater entities."""

    key: WaterHeaterType
    options_key: WaterHeaterOptionsType | None


WATERHEATER_TYPES = (
    PlugwiseWaterHeaterEntityDescription(
        key=BOILER_TEMP,
        translation_key=BOILER_TEMP,
        entity_category=EntityCategory.CONFIG,
        options_key=None,
    ),
    PlugwiseWaterHeaterEntityDescription(
        key=DHW_TEMP,
        translation_key=DHW_TEMP,
        entity_category=EntityCategory.CONFIG,
        options_key=DHW_MODES,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlugwiseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Plugwise water_heater from a config entry."""
    coordinator = entry.runtime_data

    @callback
    def _add_entities() -> None:
        """Add Entities."""
        if not coordinator.new_devices:
            return

        async_add_entities(
            PlugwiseWaterHeaterEntity(coordinator, device_id, description)
            for device_id in coordinator.new_devices
            for description in WATERHEATER_TYPES
            if description.key in coordinator.data[device_id]
        )

    _add_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_entities))


class PlugwiseWaterHeaterEntity(PlugwiseEntity, WaterHeaterEntity):
    """Representation of a Plugwise water heater."""

    entity_description: PlugwiseWaterHeaterEntityDescription

    def __init__(
        self,
        coordinator: PlugwiseDataUpdateCoordinator,
        device_id: str,
        description: PlugwiseWaterHeaterEntityDescription,
    ) -> None:
        """Initialise the water_heater."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_max_temp = self.device[description.key][UPPER_BOUND]
        self._attr_min_temp = self.device[description.key][LOWER_BOUND]
        self._attr_supported_features = WaterHeaterEntityFeature.TARGET_TEMPERATURE
        if description.options_key is not None:
            self._attr_supported_features |= WaterHeaterEntityFeature.OPERATION_MODE
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_unique_id = f"{device_id}-{description.key}"
        dhw_modes = self.device.get(DHW_MODES, [])
        self._dhw_modes_count = len(dhw_modes)
        if description.options_key is not None and STATE_OFF in dhw_modes:
            self._attr_supported_features |= WaterHeaterEntityFeature.ON_OFF

    @property
    @override
    def current_operation(self) -> str | None:
        """Return current readable operation mode."""
        if self.entity_description.options_key is None:
            return STATE_ON
        return self.device.get(DHW_MODE)

    @property
    @override
    def current_temperature(self) -> float | None:
        """Return the current water temperature."""
        return self.device[self.entity_description.key].get("current")

    @property
    @override
    def operation_list(self) -> list[str] | None:
        """Return the list of available operation modes."""
        if (key := self.entity_description.options_key) is not None:
            return self.device.get(key, [])

        return None  # pragma: no cover

    @property
    @override
    def target_temperature(self) -> float | None:
        """Return the water temperature we try to reach."""
        return self.device[self.entity_description.key].get("setpoint")

    @plugwise_command
    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self.coordinator.api.set_number(
                self._dev_id,
                self.entity_description.key,
                float(temperature),
            )

    @plugwise_command
    @override
    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set the operation mode."""
        await self.coordinator.api.set_dhw_mode(
            DHW_MODE, self._dev_id, self._dhw_modes_count, operation_mode
        )

    @plugwise_command
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the water_heater off."""
        await self.coordinator.api.set_dhw_mode(
            DHW_MODE, self._dev_id, self._dhw_modes_count, STATE_OFF
        )

    @plugwise_command
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the water_heater on and set the operation mode."""
        await self.coordinator.api.set_dhw_mode(
            DHW_MODE, self._dev_id, self._dhw_modes_count, STATE_ECO
        )
