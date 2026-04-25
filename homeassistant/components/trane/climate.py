"""Climate platform for the Trane Local integration."""

from __future__ import annotations

from typing import Any

from steamloop import FanMode, HoldType, ThermostatConnection, ZoneMode

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import TraneZoneEntity
from .types import TraneConfigEntry

PARALLEL_UPDATES = 0

HA_TO_ZONE_MODE = {
    HVACMode.OFF: ZoneMode.OFF,
    HVACMode.HEAT: ZoneMode.HEAT,
    HVACMode.COOL: ZoneMode.COOL,
    HVACMode.HEAT_COOL: ZoneMode.AUTO,
    HVACMode.AUTO: ZoneMode.AUTO,
}

ZONE_MODE_TO_HA = {
    ZoneMode.OFF: HVACMode.OFF,
    ZoneMode.HEAT: HVACMode.HEAT,
    ZoneMode.COOL: HVACMode.COOL,
    ZoneMode.AUTO: HVACMode.AUTO,
}

HA_TO_FAN_MODE = {
    "auto": FanMode.AUTO,
    "on": FanMode.ALWAYS_ON,
    "circulate": FanMode.CIRCULATE,
}

FAN_MODE_TO_HA = {v: k for k, v in HA_TO_FAN_MODE.items()}

SINGLE_SETPOINT_MODES = frozenset({ZoneMode.COOL, ZoneMode.HEAT})


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TraneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Trane Local climate entities."""
    conn = config_entry.runtime_data
    async_add_entities(
        TraneClimateEntity(conn, config_entry.entry_id, zone_id)
        for zone_id in conn.state.zones
    )


class TraneClimateEntity(TraneZoneEntity, ClimateEntity):
    """Climate entity for a Trane thermostat zone."""

    _attr_name = None
    _attr_translation_key = "zone"
    _attr_fan_modes = list(HA_TO_FAN_MODE)
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_target_temperature_step = 1.0

    def __init__(self, conn: ThermostatConnection, entry_id: str, zone_id: str) -> None:
        """Initialize the climate entity."""
        super().__init__(conn, entry_id, zone_id, "zone")
        modes: list[HVACMode] = []
        for zone_mode in conn.state.supported_modes:
            ha_mode = ZONE_MODE_TO_HA.get(zone_mode)
            if ha_mode is None:
                continue
            modes.append(ha_mode)
            # AUTO in steamloop maps to both AUTO (schedule) and HEAT_COOL (manual hold)
            if zone_mode == ZoneMode.AUTO:
                modes.append(HVACMode.HEAT_COOL)
        self._attr_hvac_modes = modes

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        # indoor_temperature is a string from the protocol (e.g. "72.00")
        # or empty string if not yet received
        if temp := self._zone.indoor_temperature:
            return float(temp)
        return None

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        # relative_humidity is a string from the protocol (e.g. "45")
        # or empty string if not yet received
        if humidity := self._conn.state.relative_humidity:
            return int(humidity)
        return None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        zone = self._zone
        if zone.mode == ZoneMode.AUTO and zone.hold_type == HoldType.MANUAL:
            return HVACMode.HEAT_COOL
        return ZONE_MODE_TO_HA.get(zone.mode, HVACMode.OFF)

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current HVAC action."""
        # heating_active and cooling_active are system-level strings from the
        # protocol ("0"=off, "1"=idle, "2"=running); filter by zone mode so
        # a zone in COOL never reports HEATING and vice versa
        zone_mode = self._zone.mode
        if zone_mode == ZoneMode.OFF:
            return HVACAction.OFF
        state = self._conn.state
        if zone_mode != ZoneMode.HEAT and state.cooling_active == "2":
            return HVACAction.COOLING
        if zone_mode != ZoneMode.COOL and state.heating_active == "2":
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def target_temperature(self) -> float | None:
        """Return target temperature for single-setpoint modes."""
        # Setpoints are strings from the protocol or empty string if not yet received
        zone = self._zone
        if zone.mode == ZoneMode.COOL:
            return float(zone.cool_setpoint) if zone.cool_setpoint else None
        if zone.mode == ZoneMode.HEAT:
            return float(zone.heat_setpoint) if zone.heat_setpoint else None
        return None

    @property
    def target_temperature_high(self) -> float | None:
        """Return the upper bound target temperature."""
        zone = self._zone
        if zone.mode in SINGLE_SETPOINT_MODES:
            return None
        return float(zone.cool_setpoint) if zone.cool_setpoint else None

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lower bound target temperature."""
        zone = self._zone
        if zone.mode in SINGLE_SETPOINT_MODES:
            return None
        return float(zone.heat_setpoint) if zone.heat_setpoint else None

    @property
    def fan_mode(self) -> str:
        """Return the current fan mode."""
        return FAN_MODE_TO_HA.get(self._conn.state.fan_mode, "auto")

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            self._conn.set_zone_mode(self._zone_id, ZoneMode.OFF)
            return

        hold_type = HoldType.SCHEDULE if hvac_mode == HVACMode.AUTO else HoldType.MANUAL
        self._conn.set_temperature_setpoint(self._zone_id, hold_type=hold_type)

        self._conn.set_zone_mode(self._zone_id, HA_TO_ZONE_MODE[hvac_mode])

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        heat_temp = kwargs.get(ATTR_TARGET_TEMP_LOW)
        cool_temp = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        set_temp = kwargs.get(ATTR_TEMPERATURE)

        if set_temp is not None:
            if self._zone.mode == ZoneMode.COOL:
                cool_temp = set_temp
            elif self._zone.mode == ZoneMode.HEAT:
                heat_temp = set_temp

        self._conn.set_temperature_setpoint(
            self._zone_id,
            heat_setpoint=str(round(heat_temp)) if heat_temp is not None else None,
            cool_setpoint=str(round(cool_temp)) if cool_temp is not None else None,
        )

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""
        self._conn.set_fan_mode(HA_TO_FAN_MODE[fan_mode])
