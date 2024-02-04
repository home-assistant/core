"""Climate platform for Advantage Air integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ADVANTAGE_AIR_AUTOFAN_ENABLED,
    ADVANTAGE_AIR_STATE_CLOSE,
    ADVANTAGE_AIR_STATE_OFF,
    ADVANTAGE_AIR_STATE_ON,
    ADVANTAGE_AIR_STATE_OPEN,
    DOMAIN as ADVANTAGE_AIR_DOMAIN,
)
from .entity import AdvantageAirAcEntity, AdvantageAirZoneEntity
from .models import AdvantageAirData

ADVANTAGE_AIR_HVAC_MODES = {
    "heat": HVACMode.HEAT,
    "cool": HVACMode.COOL,
    "vent": HVACMode.FAN_ONLY,
    "dry": HVACMode.DRY,
    "myauto": HVACMode.HEAT_COOL,
}
HASS_HVAC_MODES = {v: k for k, v in ADVANTAGE_AIR_HVAC_MODES.items()}

ADVANTAGE_AIR_MYZONE = "MyZone"
ADVANTAGE_AIR_MYAUTO = "MyAuto"
ADVANTAGE_AIR_MYAUTO_ENABLED = "myAutoModeEnabled"
ADVANTAGE_AIR_MYTEMP = "MyTemp"
ADVANTAGE_AIR_MYTEMP_ENABLED = "climateControlModeEnabled"
ADVANTAGE_AIR_HEAT_TARGET = "myAutoHeatTargetTemp"
ADVANTAGE_AIR_COOL_TARGET = "myAutoCoolTargetTemp"
ADVANTAGE_AIR_MYFAN = "autoAA"

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AdvantageAir climate platform."""

    instance: AdvantageAirData = hass.data[ADVANTAGE_AIR_DOMAIN][config_entry.entry_id]

    entities: list[ClimateEntity] = []
    if aircons := instance.coordinator.data.get("aircons"):
        for ac_key, ac_device in aircons.items():
            entities.append(AdvantageAirAC(instance, ac_key))
            for zone_key, zone in ac_device["zones"].items():
                # Only add zone climate control when zone is in temperature control
                if zone["type"] > 0:
                    entities.append(AdvantageAirZone(instance, ac_key, zone_key))
    async_add_entities(entities)


class AdvantageAirAC(AdvantageAirAcEntity, ClimateEntity):
    """AdvantageAir AC unit."""

    _attr_fan_modes = [FAN_LOW, FAN_MEDIUM, FAN_HIGH, FAN_AUTO]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = PRECISION_WHOLE
    _attr_max_temp = 32
    _attr_min_temp = 16
    _attr_name = None
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, instance: AdvantageAirData, ac_key: str) -> None:
        """Initialize an AdvantageAir AC unit."""
        super().__init__(instance, ac_key)

        self._attr_supported_features = (
            ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )
        self._attr_hvac_modes = [
            HVACMode.OFF,
            HVACMode.COOL,
            HVACMode.HEAT,
            HVACMode.FAN_ONLY,
            HVACMode.DRY,
        ]
        # Set supported features and HVAC modes based on current operating mode
        if self._ac.get(ADVANTAGE_AIR_MYAUTO_ENABLED):
            # MyAuto
            self._attr_supported_features |= (
                ClimateEntityFeature.TARGET_TEMPERATURE
                | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            )
            self._attr_hvac_modes += [HVACMode.HEAT_COOL]
        elif not self._ac.get(ADVANTAGE_AIR_MYTEMP_ENABLED):
            # MyZone
            self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE

    @property
    def current_temperature(self) -> float | None:
        """Return the selected zones current temperature."""
        if self._myzone:
            return self._myzone["measuredTemp"]
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the current target temperature."""
        # If the system is in MyZone mode, and a zone is set, return that temperature instead.
        if (
            self._myzone
            and not self._ac.get(ADVANTAGE_AIR_MYAUTO_ENABLED)
            and not self._ac.get(ADVANTAGE_AIR_MYTEMP_ENABLED)
        ):
            return self._myzone["setTemp"]
        return self._ac["setTemp"]

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC modes."""
        if self._ac["state"] == ADVANTAGE_AIR_STATE_ON:
            return ADVANTAGE_AIR_HVAC_MODES.get(self._ac["mode"])
        return HVACMode.OFF

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan modes."""
        return FAN_AUTO if self._ac["fan"] == ADVANTAGE_AIR_MYFAN else self._ac["fan"]

    @property
    def target_temperature_high(self) -> float | None:
        """Return the temperature cool mode is enabled."""
        return self._ac.get(ADVANTAGE_AIR_COOL_TARGET)

    @property
    def target_temperature_low(self) -> float | None:
        """Return the temperature heat mode is enabled."""
        return self._ac.get(ADVANTAGE_AIR_HEAT_TARGET)

    async def async_turn_on(self) -> None:
        """Set the HVAC State to on."""
        await self.async_update_ac({"state": ADVANTAGE_AIR_STATE_ON})

    async def async_turn_off(self) -> None:
        """Set the HVAC State to off."""
        await self.async_update_ac(
            {
                "state": ADVANTAGE_AIR_STATE_OFF,
            }
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC Mode and State."""
        if hvac_mode == HVACMode.OFF:
            await self.async_update_ac({"state": ADVANTAGE_AIR_STATE_OFF})
        else:
            await self.async_update_ac(
                {
                    "state": ADVANTAGE_AIR_STATE_ON,
                    "mode": HASS_HVAC_MODES.get(hvac_mode),
                }
            )

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the Fan Mode."""
        if fan_mode == FAN_AUTO and self._ac.get(ADVANTAGE_AIR_AUTOFAN_ENABLED):
            mode = ADVANTAGE_AIR_MYFAN
        else:
            mode = fan_mode
        await self.async_update_ac({"fan": mode})

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the Temperature."""
        if ATTR_TEMPERATURE in kwargs:
            await self.async_update_ac({"setTemp": kwargs[ATTR_TEMPERATURE]})
        if ATTR_TARGET_TEMP_LOW in kwargs and ATTR_TARGET_TEMP_HIGH in kwargs:
            await self.async_update_ac(
                {
                    ADVANTAGE_AIR_COOL_TARGET: kwargs[ATTR_TARGET_TEMP_HIGH],
                    ADVANTAGE_AIR_HEAT_TARGET: kwargs[ATTR_TARGET_TEMP_LOW],
                }
            )


class AdvantageAirZone(AdvantageAirZoneEntity, ClimateEntity):
    """AdvantageAir MyTemp Zone control."""

    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT_COOL]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = PRECISION_WHOLE
    _attr_max_temp = 32
    _attr_min_temp = 16
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, instance: AdvantageAirData, ac_key: str, zone_key: str) -> None:
        """Initialize an AdvantageAir Zone control."""
        super().__init__(instance, ac_key, zone_key)
        self._attr_name = self._zone["name"]

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current state as HVAC mode."""
        if self._zone["state"] == ADVANTAGE_AIR_STATE_OPEN:
            return HVACMode.HEAT_COOL
        return HVACMode.OFF

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._zone["measuredTemp"]

    @property
    def target_temperature(self) -> float:
        """Return the target temperature."""
        return self._zone["setTemp"]

    async def async_turn_on(self) -> None:
        """Set the HVAC State to on."""
        await self.async_update_zone({"state": ADVANTAGE_AIR_STATE_OPEN})

    async def async_turn_off(self) -> None:
        """Set the HVAC State to off."""
        await self.async_update_zone({"state": ADVANTAGE_AIR_STATE_CLOSE})

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC Mode and State."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        else:
            await self.async_turn_on()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the Temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        await self.async_update_zone({"setTemp": temp})
