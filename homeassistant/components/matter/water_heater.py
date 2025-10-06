"""Matter water heater platform."""

from __future__ import annotations

from typing import Any, cast

from chip.clusters import Objects as clusters
from chip.clusters.Types import Nullable
from matter_server.client.models import device_types
from matter_server.common.errors import MatterError
from matter_server.common.helpers.util import create_attribute_path_from_attribute
import voluptuous as vol

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_HIGH_DEMAND,
    STATE_OFF,
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
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SERVICE_WATER_HEATER_BOOST
from .entity import MatterEntity
from .helpers import get_matter
from .models import MatterDiscoverySchema

TEMPERATURE_SCALING_FACTOR = 100

# Map HA WH system mode to Matter ThermostatRunningMode attribute of the Thermostat cluster (Heat = 4)
WATER_HEATER_SYSTEM_MODE_MAP = {
    STATE_ECO: 4,
    STATE_HIGH_DEMAND: 4,
    STATE_OFF: 0,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Matter WaterHeater platform from Config Entry."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.WATER_HEATER, async_add_entities)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_WATER_HEATER_BOOST,
        schema={
            # duration >=1
            vol.Required("duration"): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Optional("emergency_boost"): cv.boolean,
            vol.Optional("temporary_setpoint"): vol.All(
                vol.Coerce(int), vol.Range(min=30, max=65)
            ),
        },
        func="async_set_boost",
        supports_response=SupportsResponse.NONE,
    )


class MatterWaterHeater(MatterEntity, WaterHeaterEntity):
    """Representation of a Matter WaterHeater entity."""

    _attr_current_temperature: float | None = None
    _attr_current_operation: str
    _attr_operation_list = [
        STATE_ECO,
        STATE_HIGH_DEMAND,
        STATE_OFF,
    ]
    _attr_precision = PRECISION_WHOLE
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.ON_OFF
        | WaterHeaterEntityFeature.OPERATION_MODE
    )
    _attr_target_temperature: float | None = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    duration = 3600  # 1 hour
    _platform_translation_key = "water_heater"

    async def async_set_boost(
        self,
        duration: int,
        emergency_boost: bool = False,
        temporary_setpoint: int = Nullable,
    ) -> None:
        """Set boost."""
        self.duration = duration
        boost_info: type[
            clusters.WaterHeaterManagement.Structs.WaterHeaterBoostInfoStruct
        ] = clusters.WaterHeaterManagement.Structs.WaterHeaterBoostInfoStruct(
            duration=self.duration,
            emergencyBoost=emergency_boost,
            temporarySetpoint=temporary_setpoint * TEMPERATURE_SCALING_FACTOR
            if temporary_setpoint is not Nullable
            else Nullable,
        )
        try:
            await self.send_device_command(
                clusters.WaterHeaterManagement.Commands.Boost(boostInfo=boost_info)
            )
        except MatterError as err:
            raise HomeAssistantError(f"Error sending Boost command: {err}") from err
        self._update_from_device()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        target_temperature: float | None = kwargs.get(ATTR_TEMPERATURE)
        if (
            target_temperature is not None
            and self.target_temperature != target_temperature
        ):
            matter_attribute = clusters.Thermostat.Attributes.OccupiedHeatingSetpoint
            await self.write_attribute(
                value=round(target_temperature * TEMPERATURE_SCALING_FACTOR),
                matter_attribute=matter_attribute,
            )

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        self._attr_current_operation = operation_mode
        # Boost 1h (3600s)
        boost_info: type[
            clusters.WaterHeaterManagement.Structs.WaterHeaterBoostInfoStruct
        ] = clusters.WaterHeaterManagement.Structs.WaterHeaterBoostInfoStruct(
            duration=self.duration
        )
        system_mode_value = WATER_HEATER_SYSTEM_MODE_MAP[operation_mode]
        await self.write_attribute(
            value=system_mode_value,
            matter_attribute=clusters.Thermostat.Attributes.SystemMode,
        )
        system_mode_path = create_attribute_path_from_attribute(
            endpoint_id=self._endpoint.endpoint_id,
            attribute=clusters.Thermostat.Attributes.SystemMode,
        )
        self._endpoint.set_attribute_value(system_mode_path, system_mode_value)
        self._update_from_device()
        # Trigger Boost command
        if operation_mode == STATE_HIGH_DEMAND:
            await self.send_device_command(
                clusters.WaterHeaterManagement.Commands.Boost(boostInfo=boost_info)
            )
        # Trigger CancelBoost command for other modes
        else:
            await self.send_device_command(
                clusters.WaterHeaterManagement.Commands.CancelBoost()
            )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on water heater."""
        await self.async_set_operation_mode("eco")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off water heater."""
        await self.async_set_operation_mode("off")

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        self._attr_current_temperature = self._get_temperature_in_degrees(
            clusters.Thermostat.Attributes.LocalTemperature
        )
        self._attr_target_temperature = self._get_temperature_in_degrees(
            clusters.Thermostat.Attributes.OccupiedHeatingSetpoint
        )
        boost_state = self.get_matter_attribute_value(
            clusters.WaterHeaterManagement.Attributes.BoostState
        )
        if boost_state == clusters.WaterHeaterManagement.Enums.BoostStateEnum.kActive:
            self._attr_current_operation = STATE_HIGH_DEMAND
        else:
            self._attr_current_operation = STATE_ECO
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

    @callback
    def _get_temperature_in_degrees(
        self, attribute: type[clusters.ClusterAttributeDescriptor]
    ) -> float | None:
        """Return the scaled temperature value for the given attribute."""
        if (value := self.get_matter_attribute_value(attribute)) is not None:
            return float(value) / TEMPERATURE_SCALING_FACTOR
        return None


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
