"""Matter water heater platform."""

from __future__ import annotations

from enum import IntEnum
from typing import Any

from chip.clusters import Objects as clusters
from matter_server.client.models import device_types
from matter_server.common.helpers.util import create_attribute_path_from_attribute

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_ELECTRIC,
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
    STATE_OFF,
    STATE_ON,
    Platform,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.temperature import display_temp as show_temp

from .entity import MatterEntity
from .helpers import get_matter
from .models import MatterDiscoverySchema

SUPPORT_FLAGS_HEATER = (
    WaterHeaterEntityFeature.TARGET_TEMPERATURE
    | WaterHeaterEntityFeature.ON_OFF
    | WaterHeaterEntityFeature.OPERATION_MODE
    | WaterHeaterEntityFeature.AWAY_MODE
)


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
    _attr_min_temp = 30.0 # Replace with dynamic attribute
    _attr_max_temp = 70.0 # Replace with dynamic attribute
    _attr_precision = PRECISION_WHOLE

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )
    _attr_operation_list = [
        STATE_ECO,
        STATE_OFF,
        STATE_PERFORMANCE,
        STATE_ELECTRIC,
    ]

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


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.WATER_HEATER,
        entity_description=WaterHeaterEntityDescription(
            key="MatterWaterHeater",
            name=None,
        ),
        entity_class=MatterWaterHeater,
        required_attributes=(
            clusters.WaterHeaterManagement.Attributes.BoostState,
            clusters.WaterHeaterManagement.Attributes.HeaterTypes,
            clusters.WaterHeaterManagement.Attributes.HeatDemand,
            clusters.WaterHeaterManagement.Attributes.FeatureMap,
        ),
        optional_attributes=(),
        allow_multi=True,  # also used for sensor entity
    ),
]
