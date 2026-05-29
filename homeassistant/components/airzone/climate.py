"""Support for the Airzone climate."""

from typing import Any, Final

from aioairzone.common import OperationAction, OperationMode
from aioairzone.const import (
    API_COOL_SET_POINT,
    API_HEAT_SET_POINT,
    API_MODE,
    API_ON,
    API_SET_POINT,
    API_SPEED,
    API_SYSTEM_ID,
    API_ZONE_ID,
    AZD_ACTION,
    AZD_COOL_TEMP_SET,
    AZD_DOUBLE_SET_POINT,
    AZD_HEAT_TEMP_SET,
    AZD_HUMIDITY,
    AZD_ID,
    AZD_MASTER,
    AZD_MODE,
    AZD_MODES,
    AZD_ON,
    AZD_SPEED,
    AZD_SPEEDS,
    AZD_SYSTEM,
    AZD_SYSTEMS,
    AZD_TEMP,
    AZD_TEMP_MAX,
    AZD_TEMP_MIN,
    AZD_TEMP_SET,
    AZD_TEMP_UNIT,
    AZD_ZONES,
)
from aioairzone.exceptions import AirzoneError

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
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import API_TEMPERATURE_STEP, TEMP_UNIT_LIB_TO_HASS
from .coordinator import AirzoneConfigEntry, AirzoneUpdateCoordinator
from .entity import AirzoneSystemEntity, AirzoneZoneEntity

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
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add Airzone climate from a config_entry."""
    coordinator = entry.runtime_data

    added_systems: set[str] = set()
    added_zones: set[str] = set()

    def _async_entity_listener() -> None:
        """Handle additions of climate."""

        entities: list[ClimateEntity] = []

        systems_data = coordinator.data.get(AZD_SYSTEMS, {})
        received_systems = set(systems_data)
        new_systems = received_systems - added_systems
        if new_systems:
            entities.extend(
                AirzoneSystemClimate(
                    coordinator,
                    entry,
                    system_id,
                    systems_data.get(system_id),
                )
                for system_id in new_systems
            )
            added_systems.update(new_systems)

        zones_data = coordinator.data.get(AZD_ZONES, {})
        received_zones = set(zones_data)
        new_zones = received_zones - added_zones
        if new_zones:
            entities.extend(
                AirzoneClimate(
                    coordinator,
                    entry,
                    system_zone_id,
                    zones_data.get(system_zone_id),
                )
                for system_zone_id in new_zones
            )
            added_zones.update(new_zones)

        async_add_entities(entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_entity_listener))
    _async_entity_listener()


class AirzoneClimate(AirzoneZoneEntity, ClimateEntity):
    """Define an Airzone sensor."""

    _attr_name = None
    _speeds: dict[int, str] = {}
    _speeds_reverse: dict[str, int] = {}

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
        self._is_master = bool(self.get_airzone_value(AZD_MASTER))
        if self._is_master:
            _attr_hvac_modes = [
                HVAC_MODE_LIB_TO_HASS[mode]
                for mode in self.get_airzone_value(AZD_MODES)
            ]
            self._attr_hvac_modes = list(dict.fromkeys(_attr_hvac_modes))
        else:
            self._update_slave_hvac_modes()
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

    def _update_slave_hvac_modes(self) -> None:
        modes = [HVACMode.OFF]
        current = HVAC_MODE_LIB_TO_HASS.get(self.get_airzone_value(AZD_MODE))
        if current is not None and current != HVACMode.OFF:
            modes.append(current)
        self._attr_hvac_modes = modes

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
        params = {}
        if hvac_mode == HVACMode.OFF:
            params[API_ON] = 0
        else:
            mode = HVAC_MODE_HASS_TO_LIB[hvac_mode]
            # The mode is system-wide; it can only be changed on the master zone.
            # Slave zones only expose off and the current mode.
            if mode != self.get_airzone_value(AZD_MODE) and self.get_airzone_value(
                AZD_MASTER
            ):
                params[API_MODE] = mode
            params[API_ON] = 1
        await self._async_update_hvac_params(params)

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
        if not self._is_master:
            self._update_slave_hvac_modes()
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


class AirzoneSystemClimate(AirzoneSystemEntity, ClimateEntity):
    """Define an Airzone global (all zones) climate."""

    _attr_translation_key = "all_zones"
    _speeds: dict[int, str]
    _speeds_reverse: dict[str, int]

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        entry: ConfigEntry,
        system_id: str,
        system_data: dict[str, Any],
    ) -> None:
        """Initialize Airzone global climate entity."""
        super().__init__(coordinator, entry, system_data)

        self._speeds = {}
        self._speeds_reverse = {}

        self._attr_unique_id = f"{self._attr_unique_id}_{system_id}_all_zones"
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )
        self._attr_target_temperature_step = API_TEMPERATURE_STEP
        self._attr_temperature_unit = TEMP_UNIT_LIB_TO_HASS[
            self._master_value(AZD_TEMP_UNIT)
        ]

        modes = self._master_value(AZD_MODES) or []
        hvac_modes = [HVAC_MODE_LIB_TO_HASS[mode] for mode in modes]
        self._attr_hvac_modes = list(dict.fromkeys(hvac_modes)) or [HVACMode.OFF]

        if (
            self._master_value(AZD_SPEED) is not None
            and self._master_value(AZD_SPEEDS) is not None
        ):
            self._set_fan_speeds()
        if self._master_value(AZD_DOUBLE_SET_POINT):
            self._attr_supported_features |= (
                ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            )

        self._async_update_attrs()

    def _system_zones(self) -> list[dict[str, Any]]:
        """Return the data of every zone belonging to this system."""
        zones = self.coordinator.data.get(AZD_ZONES, {})
        return [
            zone for zone in zones.values() if zone.get(AZD_SYSTEM) == self.system_id
        ]

    def _master_zone(self) -> dict[str, Any] | None:
        """Return the master zone of the system (fallback: first zone)."""
        zones = self._system_zones()
        for zone in zones:
            if zone.get(AZD_MASTER):
                return zone
        return zones[0] if zones else None

    def _master_value(self, key: str) -> Any:
        """Return a value from the master zone."""
        zone = self._master_zone()
        return zone.get(key) if zone else None

    def _zones_average(self, key: str) -> float | None:
        """Return the average of a numeric key across all zones."""
        values: list[float] = [
            zone[key] for zone in self._system_zones() if zone.get(key) is not None
        ]
        if not values:
            return None
        return round(sum(values) / len(values), 1)

    def _set_fan_speeds(self) -> None:
        self._attr_supported_features |= ClimateEntityFeature.FAN_MODE

        speeds = self._master_value(AZD_SPEEDS)
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

    async def _async_set_zones_params(
        self, zones: list[dict[str, Any]], params: dict[str, Any]
    ) -> None:
        """Send the same HVAC parameters to each given zone (fan-out)."""
        try:
            for zone in zones:
                _params = {
                    API_SYSTEM_ID: zone[AZD_SYSTEM],
                    API_ZONE_ID: zone[AZD_ID],
                    **params,
                }
                await self.coordinator.airzone.set_hvac_parameters(_params)
        except AirzoneError as error:
            raise HomeAssistantError(
                f"Failed to set system {self.entity_id}: {error}"
            ) from error

        self.coordinator.async_set_updated_data(self.coordinator.airzone.data())

    async def async_turn_on(self) -> None:
        """Turn all zones on."""
        await self._async_set_zones_params(self._system_zones(), {API_ON: 1})

    async def async_turn_off(self) -> None:
        """Turn all zones off."""
        await self._async_set_zones_params(self._system_zones(), {API_ON: 0})

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode on every zone that supports speeds."""
        speed = self._speeds_reverse.get(fan_mode)
        zones = [
            zone for zone in self._system_zones() if zone.get(AZD_SPEEDS) is not None
        ]
        await self._async_set_zones_params(zones, {API_SPEED: speed})

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode for all zones."""
        if hvac_mode == HVACMode.OFF:
            await self._async_set_zones_params(self._system_zones(), {API_ON: 0})
            return

        mode = HVAC_MODE_HASS_TO_LIB[hvac_mode]
        # The mode is system-wide and can only be set on the master zone.
        if mode != self._master_value(AZD_MODE):
            master = self._master_zone()
            if master is not None:
                await self._async_set_zones_params(
                    [master], {API_MODE: mode, API_ON: 1}
                )
        await self._async_set_zones_params(self._system_zones(), {API_ON: 1})

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a common target temperature for all zones."""
        params: dict[str, Any] = {}
        if ATTR_TEMPERATURE in kwargs:
            params[API_SET_POINT] = kwargs[ATTR_TEMPERATURE]
        if ATTR_TARGET_TEMP_LOW in kwargs and ATTR_TARGET_TEMP_HIGH in kwargs:
            params[API_COOL_SET_POINT] = kwargs[ATTR_TARGET_TEMP_HIGH]
            params[API_HEAT_SET_POINT] = kwargs[ATTR_TARGET_TEMP_LOW]
        if params:
            await self._async_set_zones_params(self._system_zones(), params)

        if ATTR_HVAC_MODE in kwargs:
            await self.async_set_hvac_mode(kwargs[ATTR_HVAC_MODE])

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Update global climate attributes."""
        self._attr_current_temperature = self._zones_average(AZD_TEMP)
        humidity = self._zones_average(AZD_HUMIDITY)
        self._attr_current_humidity = round(humidity) if humidity is not None else None

        action = self._master_value(AZD_ACTION)
        self._attr_hvac_action = (
            HVAC_ACTION_LIB_TO_HASS.get(action) if action is not None else None
        )

        if any(zone.get(AZD_ON) for zone in self._system_zones()):
            self._attr_hvac_mode = HVAC_MODE_LIB_TO_HASS.get(
                self._master_value(AZD_MODE)
            )
        else:
            self._attr_hvac_mode = HVACMode.OFF

        self._attr_max_temp = self._master_value(AZD_TEMP_MAX)
        self._attr_min_temp = self._master_value(AZD_TEMP_MIN)

        if self.supported_features & ClimateEntityFeature.FAN_MODE:
            self._attr_fan_mode = self._speeds.get(self._master_value(AZD_SPEED))

        if (
            self.supported_features & ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            and self._attr_hvac_mode == HVACMode.HEAT_COOL
        ):
            self._attr_target_temperature_high = self._master_value(AZD_COOL_TEMP_SET)
            self._attr_target_temperature_low = self._master_value(AZD_HEAT_TEMP_SET)
            self._attr_target_temperature = None
        else:
            self._attr_target_temperature_high = None
            self._attr_target_temperature_low = None
            self._attr_target_temperature = self._master_value(AZD_TEMP_SET)
