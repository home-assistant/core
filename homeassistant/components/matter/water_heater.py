"""Matter water heater platform."""

from __future__ import annotations

from typing import Any, cast

from chip.clusters import Objects as clusters
from matter_server.client.models import device_types

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_ELECTRIC,
    STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND,
    STATE_OFF,
    STATE_PERFORMANCE,
    WaterHeaterEntity,
    WaterHeaterEntityDescription,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_WHOLE,
    Platform,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import MatterEntity
from .helpers import get_matter
from .models import MatterDiscoverySchema

SUPPORT_FLAGS_HEATER = (
    WaterHeaterEntityFeature.TARGET_TEMPERATURE
    | WaterHeaterEntityFeature.ON_OFF
    | WaterHeaterEntityFeature.OPERATION_MODE
)
TEMPERATURE_SCALING_FACTOR = 100


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Matter WaterHeater platform from Config Entry."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.WATER_HEATER, async_add_entities)


class MatterWaterHeater(MatterEntity, WaterHeaterEntity):
    """Representation of a Matter WaterHeater entity."""

    _attr_current_temperature: float | None = None
    # _attr_min_temp: float | None = None
    # _attr_max_temp: float | None = None
    _attr_operation_list = [
        STATE_ECO,
        STATE_ELECTRIC,
        STATE_HEAT_PUMP,
        STATE_HIGH_DEMAND,
        STATE_OFF,
        STATE_PERFORMANCE,
    ]
    _attr_precision = PRECISION_WHOLE
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )
    _attr_target_temperature: float | None = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _platform_translation_key = "water_heater"

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        self._attr_target_temperature = kwargs.get(ATTR_TEMPERATURE)
        self.schedule_update_ha_state()

    def set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        self._attr_current_operation = operation_mode
        self.schedule_update_ha_state()

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on water heater."""
        self.set_operation_mode("eco")

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off water heater."""
        self.set_operation_mode("off")

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        # self._calculate_features()
        self._attr_current_temperature = self._get_temperature_in_degrees(
            clusters.Thermostat.Attributes.LocalTemperature
        )
        self._attr_temperature = cast(
            float,
            self._get_temperature_in_degrees(
                clusters.Thermostat.Attributes.OccupiedHeatingSetpoint
            ),
        )
        self._attr_min_temp = cast(
            float,
            self._get_temperature_in_degrees(
                clusters.Thermostat.Attributes.AbsMinHeatSetpointLimit
            ),
        )
        self._attr_max_temp = cast(
            float,
            self._get_temperature_in_degrees(
                clusters.Thermostat.Attributes.AbsMaxHeatSetpointLimit
            ),
        )
        # self._attr_operation_mode = STATE_HEAT_PUMP

    @callback
    def _get_temperature_in_degrees(
        self, attribute: type[clusters.ClusterAttributeDescriptor]
    ) -> float | None:
        """Return the scaled temperature value for the given attribute."""
        if value := self.get_matter_attribute_value(attribute):
            return float(value) / TEMPERATURE_SCALING_FACTOR
        return None


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.WATER_HEATER,
        entity_description=WaterHeaterEntityDescription(
            key="MatterWaterHeater",
        ),
        entity_class=MatterWaterHeater,
        required_attributes=(
            clusters.Thermostat.Attributes.OccupiedHeatingSetpoint,
            clusters.Thermostat.Attributes.AbsMinHeatSetpointLimit,
            clusters.Thermostat.Attributes.AbsMaxHeatSetpointLimit,
            clusters.Thermostat.Attributes.LocalTemperature,
            clusters.WaterHeaterManagement.Attributes.FeatureMap,
        ),
        optional_attributes=(
            clusters.WaterHeaterManagement.Attributes.HeaterTypes,
            clusters.WaterHeaterManagement.Attributes.BoostState,
            clusters.WaterHeaterManagement.Attributes.HeatDemand,
        ),
        device_type=(device_types.WaterHeater,),
        allow_multi=True,  # also used for sensor entity
    ),
]
