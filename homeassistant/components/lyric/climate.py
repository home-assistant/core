"""Support for Honeywell Lyric climate platform."""
from __future__ import annotations

import asyncio
import logging
from time import localtime, strftime, time
from typing import Any

from aiolyric import Lyric
from aiolyric.objects.device import LyricDevice
from aiolyric.objects.location import LyricLocation
import voluptuous as vol

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import LyricDeviceEntity
from .const import (
    DOMAIN,
    LYRIC_EXCEPTIONS,
    PRESET_HOLD_UNTIL,
    PRESET_NO_HOLD,
    PRESET_PERMANENT_HOLD,
    PRESET_TEMPORARY_HOLD,
    PRESET_VACATION_HOLD,
)

_LOGGER = logging.getLogger(__name__)

# Only LCC models support presets
SUPPORT_FLAGS_LCC = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.PRESET_MODE
    | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
)
SUPPORT_FLAGS_TCC = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
)

LYRIC_HVAC_ACTION_OFF = "EquipmentOff"
LYRIC_HVAC_ACTION_HEAT = "Heat"
LYRIC_HVAC_ACTION_COOL = "Cool"

LYRIC_HVAC_MODE_OFF = "Off"
LYRIC_HVAC_MODE_HEAT = "Heat"
LYRIC_HVAC_MODE_COOL = "Cool"
LYRIC_HVAC_MODE_HEAT_COOL = "Auto"

LYRIC_HVAC_MODES = {
    HVACMode.OFF: LYRIC_HVAC_MODE_OFF,
    HVACMode.HEAT: LYRIC_HVAC_MODE_HEAT,
    HVACMode.COOL: LYRIC_HVAC_MODE_COOL,
    HVACMode.HEAT_COOL: LYRIC_HVAC_MODE_HEAT_COOL,
}

HVAC_MODES = {
    LYRIC_HVAC_MODE_OFF: HVACMode.OFF,
    LYRIC_HVAC_MODE_HEAT: HVACMode.HEAT,
    LYRIC_HVAC_MODE_COOL: HVACMode.COOL,
    LYRIC_HVAC_MODE_HEAT_COOL: HVACMode.HEAT_COOL,
}

HVAC_ACTIONS = {
    LYRIC_HVAC_ACTION_OFF: HVACAction.OFF,
    LYRIC_HVAC_ACTION_HEAT: HVACAction.HEATING,
    LYRIC_HVAC_ACTION_COOL: HVACAction.COOLING,
}

SERVICE_HOLD_TIME = "set_hold_time"
ATTR_TIME_PERIOD = "time_period"

SCHEMA_HOLD_TIME = {
    vol.Required(ATTR_TIME_PERIOD, default="01:00:00"): vol.All(
        cv.time_period,
        cv.positive_timedelta,
        lambda td: strftime("%H:%M:%S", localtime(time() + td.total_seconds())),
    )
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Honeywell Lyric climate platform based on a config entry."""
    coordinator: DataUpdateCoordinator[Lyric] = hass.data[DOMAIN][entry.entry_id]

    entities = []

    for location in coordinator.data.locations:
        for device in location.devices:
            entities.append(
                LyricClimate(
                    coordinator,
                    ClimateEntityDescription(
                        key=f"{device.macID}_thermostat",
                        name=device.name,
                    ),
                    location,
                    device,
                    hass.config.units.temperature_unit,
                )
            )

    async_add_entities(entities, True)

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_HOLD_TIME,
        SCHEMA_HOLD_TIME,
        "async_set_hold_time",
    )


class LyricClimate(LyricDeviceEntity, ClimateEntity):
    """Defines a Honeywell Lyric climate entity."""

    coordinator: DataUpdateCoordinator[Lyric]
    entity_description: ClimateEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Lyric],
        description: ClimateEntityDescription,
        location: LyricLocation,
        device: LyricDevice,
        temperature_unit: str,
    ) -> None:
        """Initialize Honeywell Lyric climate entity."""
        self._temperature_unit = temperature_unit

        # Setup supported hvac modes
        self._attr_hvac_modes = [HVACMode.OFF]

        # Add supported lyric thermostat features
        if LYRIC_HVAC_MODE_HEAT in device.allowedModes:
            self._attr_hvac_modes.append(HVACMode.HEAT)

        if LYRIC_HVAC_MODE_COOL in device.allowedModes:
            self._attr_hvac_modes.append(HVACMode.COOL)

        if (
            LYRIC_HVAC_MODE_HEAT in device.allowedModes
            and LYRIC_HVAC_MODE_COOL in device.allowedModes
        ):
            self._attr_hvac_modes.append(HVACMode.HEAT_COOL)

        super().__init__(
            coordinator,
            location,
            device,
            f"{device.macID}_thermostat",
        )
        self.entity_description = description

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        if self.device.changeableValues.thermostatSetpointStatus:
            return SUPPORT_FLAGS_LCC
        return SUPPORT_FLAGS_TCC

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return self._temperature_unit

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.device.indoorTemperature

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current hvac action."""
        action = HVAC_ACTIONS.get(self.device.operationStatus.mode, None)
        if action == HVACAction.OFF and self.hvac_mode != HVACMode.OFF:
            action = HVACAction.IDLE
        return action

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the hvac mode."""
        return HVAC_MODES[self.device.changeableValues.mode]

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        device = self.device
        if (
            device.changeableValues.autoChangeoverActive
            or HVAC_MODES[device.changeableValues.mode] == HVACMode.OFF
        ):
            return None
        if self.hvac_mode == HVACMode.COOL:
            return device.changeableValues.coolSetpoint
        return device.changeableValues.heatSetpoint

    @property
    def target_temperature_high(self) -> float | None:
        """Return the highbound target temperature we try to reach."""
        device = self.device
        if (
            not device.changeableValues.autoChangeoverActive
            or HVAC_MODES[device.changeableValues.mode] == HVACMode.OFF
        ):
            return None
        return device.changeableValues.coolSetpoint

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach."""
        device = self.device
        if (
            not device.changeableValues.autoChangeoverActive
            or HVAC_MODES[device.changeableValues.mode] == HVACMode.OFF
        ):
            return None
        return device.changeableValues.heatSetpoint

    @property
    def preset_mode(self) -> str | None:
        """Return current preset mode."""
        return self.device.changeableValues.thermostatSetpointStatus

    @property
    def preset_modes(self) -> list[str] | None:
        """Return preset modes."""
        return [
            PRESET_NO_HOLD,
            PRESET_HOLD_UNTIL,
            PRESET_PERMANENT_HOLD,
            PRESET_TEMPORARY_HOLD,
            PRESET_VACATION_HOLD,
        ]

    @property
    def min_temp(self) -> float:
        """Identify min_temp in Lyric API or defaults if not available."""
        device = self.device
        if LYRIC_HVAC_MODE_COOL in device.allowedModes:
            return device.minCoolSetpoint
        return device.minHeatSetpoint

    @property
    def max_temp(self) -> float:
        """Identify max_temp in Lyric API or defaults if not available."""
        device = self.device
        if LYRIC_HVAC_MODE_HEAT in device.allowedModes:
            return device.maxHeatSetpoint
        return device.maxCoolSetpoint

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if self.hvac_mode == HVACMode.OFF:
            return

        device = self.device
        target_temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        target_temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)

        if device.changeableValues.autoChangeoverActive:
            if target_temp_low is None or target_temp_high is None:
                raise HomeAssistantError(
                    "Could not find target_temp_low and/or target_temp_high in"
                    " arguments"
                )
            _LOGGER.debug("Set temperature: %s - %s", target_temp_low, target_temp_high)
            try:
                await self._update_thermostat(
                    self.location,
                    device,
                    coolSetpoint=target_temp_high,
                    heatSetpoint=target_temp_low,
                    mode=HVAC_MODES[device.changeableValues.heatCoolMode],
                )
            except LYRIC_EXCEPTIONS as exception:
                _LOGGER.error(exception)
            await self.coordinator.async_refresh()
        else:
            temp = kwargs.get(ATTR_TEMPERATURE)
            _LOGGER.debug("Set temperature: %s", temp)
            try:
                if self.hvac_mode == HVACMode.COOL:
                    await self._update_thermostat(
                        self.location, device, coolSetpoint=temp
                    )
                else:
                    await self._update_thermostat(
                        self.location, device, heatSetpoint=temp
                    )
            except LYRIC_EXCEPTIONS as exception:
                _LOGGER.error(exception)
            await self.coordinator.async_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode."""
        _LOGGER.debug("HVAC mode: %s", hvac_mode)
        try:
            if LYRIC_HVAC_MODES[hvac_mode] == LYRIC_HVAC_MODE_HEAT_COOL:
                # If the system is off, turn it to Heat first then to Auto,
                # otherwise it turns to.
                # Auto briefly and then reverts to Off (perhaps related to
                # heatCoolMode). This is the behavior that happens with the
                # native app as well, so likely a bug in the api itself
                if HVAC_MODES[self.device.changeableValues.mode] == HVACMode.OFF:
                    _LOGGER.debug(
                        "HVAC mode passed to lyric: %s",
                        HVAC_MODES[LYRIC_HVAC_MODE_COOL],
                    )
                    await self._update_thermostat(
                        self.location,
                        self.device,
                        mode=HVAC_MODES[LYRIC_HVAC_MODE_HEAT],
                        autoChangeoverActive=False,
                    )
                    # Sleep 3 seconds before proceeding
                    await asyncio.sleep(3)
                    _LOGGER.debug(
                        "HVAC mode passed to lyric: %s",
                        HVAC_MODES[LYRIC_HVAC_MODE_HEAT],
                    )
                    await self._update_thermostat(
                        self.location,
                        self.device,
                        mode=HVAC_MODES[LYRIC_HVAC_MODE_HEAT],
                        autoChangeoverActive=True,
                    )
                else:
                    _LOGGER.debug(
                        "HVAC mode passed to lyric: %s",
                        HVAC_MODES[self.device.changeableValues.mode],
                    )
                    await self._update_thermostat(
                        self.location, self.device, autoChangeoverActive=True
                    )
            else:
                _LOGGER.debug(
                    "HVAC mode passed to lyric: %s", LYRIC_HVAC_MODES[hvac_mode]
                )
                await self._update_thermostat(
                    self.location,
                    self.device,
                    mode=LYRIC_HVAC_MODES[hvac_mode],
                    autoChangeoverActive=False,
                )
        except LYRIC_EXCEPTIONS as exception:
            _LOGGER.error(exception)
        await self.coordinator.async_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset (PermanentHold, HoldUntil, NoHold, VacationHold) mode."""
        _LOGGER.debug("Set preset mode: %s", preset_mode)
        try:
            await self._update_thermostat(
                self.location, self.device, thermostatSetpointStatus=preset_mode
            )
        except LYRIC_EXCEPTIONS as exception:
            _LOGGER.error(exception)
        await self.coordinator.async_refresh()

    async def async_set_hold_time(self, time_period: str) -> None:
        """Set the time to hold until."""
        _LOGGER.debug("set_hold_time: %s", time_period)
        try:
            await self._update_thermostat(
                self.location,
                self.device,
                thermostatSetpointStatus=PRESET_HOLD_UNTIL,
                nextPeriodTime=time_period,
            )
        except LYRIC_EXCEPTIONS as exception:
            _LOGGER.error(exception)
        await self.coordinator.async_refresh()
