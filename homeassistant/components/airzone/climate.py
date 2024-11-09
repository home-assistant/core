"""Support for the Airzone climate."""

from __future__ import annotations

from typing import Any, Final

from aioairzone.common import OperationAction, OperationMode
from aioairzone.const import (
    API_COOL_SET_POINT,
    API_HEAT_SET_POINT,
    API_MODE,
    API_ON,
    API_SET_POINT,
    API_SPEED,
    AZD_ACTION,
    AZD_COOL_TEMP_SET,
    AZD_DOUBLE_SET_POINT,
    AZD_HEAT_TEMP_SET,
    AZD_HUMIDITY,
    AZD_MASTER,
    AZD_MODE,
    AZD_MODES,
    AZD_ON,
    AZD_SPEED,
    AZD_SPEEDS,
    AZD_TEMP,
    AZD_TEMP_MAX,
    AZD_TEMP_MIN,
    AZD_TEMP_SET,
    AZD_TEMP_UNIT,
    AZD_ZONES,
)

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AirzoneConfigEntry
from .const import API_TEMPERATURE_STEP, TEMP_UNIT_LIB_TO_HASS
from .coordinator import AirzoneUpdateCoordinator
from .entity import AirzoneZoneEntity

BASE_FAN_SPEEDS: Final[dict[int, str]] = {
    0: FAN_AUTO,
    1: FAN_LOW,
}
FAN_SPEED_MAPS: Final[dict[int, dict[int, str]]] = {
    2: BASE_FAN_SPEEDS
    | {
        2: FAN_HIGH,
    },
    3: BASE_FAN_SPEEDS
    | {
        2: FAN_MEDIUM,
        3: FAN_HIGH,
    },
}

HVAC_ACTION_LIB_TO_HASS: Final[dict[OperationAction, HVACAction]] = {
    OperationAction.COOLING: HVACAction.COOLING,
    OperationAction.DRYING: HVACAction.DRYING,
    OperationAction.FAN: HVACAction.FAN,
    OperationAction.HEATING: HVACAction.HEATING,
    OperationAction.IDLE: HVACAction.IDLE,
    OperationAction.OFF: HVACAction.OFF,
}
HVAC_MODE_LIB_TO_HASS: Final[dict[OperationMode, HVACMode]] = {
    OperationMode.STOP: HVACMode.OFF,
    OperationMode.COOLING: HVACMode.COOL,
    OperationMode.HEATING: HVACMode.HEAT,
    OperationMode.FAN: HVACMode.FAN_ONLY,
    OperationMode.DRY: HVACMode.DRY,
    OperationMode.AUX_HEATING: HVACMode.HEAT,
    OperationMode.AUTO: HVACMode.HEAT_COOL,
}
HVAC_MODE_HASS_TO_LIB: Final[dict[HVACMode, OperationMode]] = {
    HVACMode.OFF: OperationMode.STOP,
    HVACMode.COOL: OperationMode.COOLING,
    HVACMode.HEAT: OperationMode.HEATING,
    HVACMode.FAN_ONLY: OperationMode.FAN,
    HVACMode.DRY: OperationMode.DRY,
    HVACMode.HEAT_COOL: OperationMode.AUTO,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirzoneConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add Airzone climate from a config_entry."""
    coordinator = entry.runtime_data

    added_zones: set[str] = set()

    def _async_entity_listener() -> None:
        """Handle additions of climate."""

        zones_data = coordinator.data.get(AZD_ZONES, {})
        received_zones = set(zones_data)
        new_zones = received_zones - added_zones
        if new_zones:
            async_add_entities(
                AirzoneClimate(
                    coordinator,
                    entry,
                    system_zone_id,
                    zones_data.get(system_zone_id),
                )
                for system_zone_id in new_zones
            )
            added_zones.update(new_zones)

    entry.async_on_unload(coordinator.async_add_listener(_async_entity_listener))
    _async_entity_listener()


class AirzoneClimate(AirzoneZoneEntity, ClimateEntity):
    """Define an Airzone sensor."""

    _attr_name = None
    _speeds: dict[int, str] = {}
    _speeds_reverse: dict[str, int] = {}
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        entry: ConfigEntry,
        system_zone_id: str,
        zone_data: dict,
    ) -> None:
        """Initialize Airzone climate entity."""
        super().__init__(coordinator, entry, system_zone_id, zone_data)

        self._attr_unique_id = f"{self._attr_unique_id}_{system_zone_id}"
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )
        self._attr_target_temperature_step = API_TEMPERATURE_STEP
        self._attr_temperature_unit = TEMP_UNIT_LIB_TO_HASS[
            self.get_airzone_value(AZD_TEMP_UNIT)
        ]
        _attr_hvac_modes = [
            HVAC_MODE_LIB_TO_HASS[mode] for mode in self.get_airzone_value(AZD_MODES)
        ]
        self._attr_hvac_modes = list(dict.fromkeys(_attr_hvac_modes))
        if (
            self.get_airzone_value(AZD_SPEED) is not None
            and self.get_airzone_value(AZD_SPEEDS) is not None
        ):
            self._set_fan_speeds()
        if self.get_airzone_value(AZD_DOUBLE_SET_POINT):
            self._attr_supported_features |= (
                ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            )

        self._async_update_attrs()

    def _set_fan_speeds(self) -> None:
        self._attr_supported_features |= ClimateEntityFeature.FAN_MODE

        speeds = self.get_airzone_value(AZD_SPEEDS)
        max_speed = max(speeds)
        if _speeds := FAN_SPEED_MAPS.get(max_speed):
            self._speeds = _speeds
        else:
            for speed in speeds:
                if speed == 0:
                    self._speeds[speed] = FAN_AUTO
                else:
                    self._speeds[speed] = f"{int(round((speed * 100) / max_speed, 0))}%"

            self._speeds[1] = FAN_LOW
            self._speeds[int(round((max_speed + 1) / 2, 0))] = FAN_MEDIUM
            self._speeds[max_speed] = FAN_HIGH

        self._speeds_reverse = {v: k for k, v in self._speeds.items()}
        self._attr_fan_modes = list(self._speeds_reverse)

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        params = {
            API_ON: 1,
        }
        await self._async_update_hvac_params(params)

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        params = {
            API_ON: 0,
        }
        await self._async_update_hvac_params(params)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        params = {
            API_SPEED: self._speeds_reverse.get(fan_mode),
        }
        await self._async_update_hvac_params(params)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode."""
        slave_raise = False

        params = {}
        if hvac_mode == HVACMode.OFF:
            params[API_ON] = 0
        else:
            mode = HVAC_MODE_HASS_TO_LIB[hvac_mode]
            if mode != self.get_airzone_value(AZD_MODE):
                if self.get_airzone_value(AZD_MASTER):
                    params[API_MODE] = mode
                else:
                    slave_raise = True
            params[API_ON] = 1
        await self._async_update_hvac_params(params)

        if slave_raise:
            raise HomeAssistantError(
                f"Mode can't be changed on slave zone {self.entity_id}"
            )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        params = {}
        if ATTR_TEMPERATURE in kwargs:
            params[API_SET_POINT] = kwargs[ATTR_TEMPERATURE]
        if ATTR_TARGET_TEMP_LOW in kwargs and ATTR_TARGET_TEMP_HIGH in kwargs:
            params[API_COOL_SET_POINT] = kwargs[ATTR_TARGET_TEMP_HIGH]
            params[API_HEAT_SET_POINT] = kwargs[ATTR_TARGET_TEMP_LOW]
        await self._async_update_hvac_params(params)

        if ATTR_HVAC_MODE in kwargs:
            await self.async_set_hvac_mode(kwargs[ATTR_HVAC_MODE])

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Update climate attributes."""
        self._attr_current_temperature = self.get_airzone_value(AZD_TEMP)
        self._attr_current_humidity = self.get_airzone_value(AZD_HUMIDITY)
        self._attr_hvac_action = HVAC_ACTION_LIB_TO_HASS[
            self.get_airzone_value(AZD_ACTION)
        ]
        if self.get_airzone_value(AZD_ON):
            self._attr_hvac_mode = HVAC_MODE_LIB_TO_HASS[
                self.get_airzone_value(AZD_MODE)
            ]
        else:
            self._attr_hvac_mode = HVACMode.OFF
        self._attr_max_temp = self.get_airzone_value(AZD_TEMP_MAX)
        self._attr_min_temp = self.get_airzone_value(AZD_TEMP_MIN)
        if self.supported_features & ClimateEntityFeature.FAN_MODE:
            self._attr_fan_mode = self._speeds.get(self.get_airzone_value(AZD_SPEED))
        if (
            self.supported_features & ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            and self._attr_hvac_mode == HVACMode.HEAT_COOL
        ):
            self._attr_target_temperature_high = self.get_airzone_value(
                AZD_COOL_TEMP_SET
            )
            self._attr_target_temperature_low = self.get_airzone_value(
                AZD_HEAT_TEMP_SET
            )
            self._attr_target_temperature = None
        else:
            self._attr_target_temperature_high = None
            self._attr_target_temperature_low = None
            self._attr_target_temperature = self.get_airzone_value(AZD_TEMP_SET)
