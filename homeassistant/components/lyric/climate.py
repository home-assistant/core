"""Support for Honeywell Lyric climate platform."""
import logging
from typing import List, Optional

from aiohttp.client_exceptions import ClientResponseError
from aiolyric.exceptions import LyricAuthenticationException, LyricException
from aiolyric.objects.device import LyricDevice
from aiolyric.objects.location import LyricLocation
import voluptuous as vol

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, ATTR_TIME
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import LyricDeviceEntity
from .const import (
    DOMAIN,
    PRESET_HOLD_UNTIL,
    PRESET_NO_HOLD,
    PRESET_PERMANENT_HOLD,
    PRESET_TEMPORARY_HOLD,
    PRESET_VACATION_HOLD,
    SERVICE_HOLD_TIME,
)

LYRIC_EXCEPTIONS = (
    LyricAuthenticationException,
    LyricException,
    ClientResponseError,
)

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

LYRIC_HVAC_MODES = {
    HVAC_MODE_OFF: "Off",
    HVAC_MODE_HEAT: "Heat",
    HVAC_MODE_COOL: "Cool",
    HVAC_MODE_HEAT_COOL: "Auto",
}

HVAC_MODES = {
    "Off": HVAC_MODE_OFF,
    "Heat": HVAC_MODE_HEAT,
    "Cool": HVAC_MODE_COOL,
    "Auto": HVAC_MODE_HEAT_COOL,
}


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Honeywell Lyric climate platform based on a config entry."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    for location in coordinator.data.locations:
        for device in location.devices:
            entities.append(LyricClimate(hass, coordinator, location, device))

    async_add_entities(entities, True)

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_HOLD_TIME,
        {vol.Required(ATTR_TIME): cv.string},
        "set_hold_time",
    )


class LyricClimate(LyricDeviceEntity, ClimateEntity):
    """Defines a Honeywell Lyric climate entity."""

    def __init__(
        self,
        hass: HomeAssistantType,
        coordinator: DataUpdateCoordinator,
        location: LyricLocation,
        device: LyricDevice,
    ) -> None:
        """Initialize Honeywell Lyric climate entity."""
        self._temperature_unit = hass.config.units.temperature_unit

        # Setup supported hvac modes
        self._hvac_modes = [HVAC_MODE_OFF]

        # Add supported lyric thermostat features
        if "Heat" in device.allowedModes:
            self._hvac_modes.append(HVAC_MODE_HEAT)

        if "Cool" in device.allowedModes:
            self._hvac_modes.append(HVAC_MODE_COOL)

        if "Heat" in device.allowedModes and "Cool" in device.allowedModes:
            self._hvac_modes.append(HVAC_MODE_HEAT_COOL)

        super().__init__(
            coordinator,
            location,
            device,
            f"{device.macID}_thermostat",
            device.name,
            "mdi:thermostat",
        )

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return self._temperature_unit

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        for location in self.coordinator.data.locations:
            for device in location.devices:
                if device.macID == self._device.macID:
                    return device.indoorTemperature

    @property
    def hvac_mode(self) -> str:
        """Return the hvac mode."""
        for location in self.coordinator.data.locations:
            for device in location.devices:
                if device.macID == self._device.macID:
                    return HVAC_MODES[device.changeableValues.mode]

    @property
    def hvac_modes(self) -> List[str]:
        """List of available hvac modes."""
        return self._hvac_modes

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the temperature we try to reach."""
        for location in self.coordinator.data.locations:
            for device in location.devices:
                if device.macID == self._device.macID:
                    if not device.hasDualSetpointStatus:
                        return device.changeableValues.heatSetpoint

    @property
    def target_temperature_low(self) -> Optional[float]:
        """Return the upper bound temperature we try to reach."""
        for location in self.coordinator.data.locations:
            for device in location.devices:
                if device.macID == self._device.macID:
                    if device.hasDualSetpointStatus:
                        return device.changeableValues.coolSetpoint

    @property
    def target_temperature_high(self) -> Optional[float]:
        """Return the upper bound temperature we try to reach."""
        for location in self.coordinator.data.locations:
            for device in location.devices:
                if device.macID == self._device.macID:
                    if device.hasDualSetpointStatus:
                        return device.changeableValues.heatSetpoint

    @property
    def preset_mode(self) -> Optional[str]:
        """Return current preset mode."""
        for location in self.coordinator.data.locations:
            for device in location.devices:
                if device.macID == self._device.macID:
                    return device.changeableValues.thermostatSetpointStatus

    @property
    def preset_modes(self) -> Optional[List[str]]:
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
        for location in self.coordinator.data.locations:
            for device in location.devices:
                if device.macID == self._device.macID:
                    return (
                        device.minCoolSetpoint
                        if "Cool" in device.allowedModes
                        else device.minHeatSetpoint
                    )

    @property
    def max_temp(self) -> float:
        """Identify max_temp in Lyric API or defaults if not available."""
        for location in self.coordinator.data.locations:
            for device in location.devices:
                if device.macID == self._device.macID:
                    return (
                        device.maxHeatSetpoint
                        if "Heat" in device.allowedModes
                        else device.maxCoolSetpoint
                    )

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        target_temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        target_temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)

        for location in self.coordinator.data.locations:
            for device in location.devices:
                if device.macID == self._device.macID:
                    if device.hasDualSetpointStatus:
                        if target_temp_low is not None and target_temp_high is not None:
                            temp = (target_temp_low, target_temp_high)
                    else:
                        temp = kwargs.get(ATTR_TEMPERATURE)
                    _LOGGER.debug("Set temperature: %s", temp)
                    try:
                        await self.coordinator.data.update_thermostat(
                            location, device, heatSetpoint=temp
                        )
                    except LYRIC_EXCEPTIONS as exception:
                        _LOGGER.error(exception)
        await self.coordinator.async_refresh()

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set hvac mode."""
        for location in self.coordinator.data.locations:
            for device in location.devices:
                if device.macID == self._device.macID:
                    _LOGGER.debug("Set hvac mode: %s", hvac_mode)
                    try:
                        await self.coordinator.data.update_thermostat(
                            location, device, mode=LYRIC_HVAC_MODES[hvac_mode]
                        )
                    except LYRIC_EXCEPTIONS as exception:
                        _LOGGER.error(exception)
        await self.coordinator.async_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset (PermanentHold, HoldUntil, NoHold, VacationHold) mode."""
        for location in self.coordinator.data.locations:
            for device in location.devices:
                if device.macID == self._device.macID:
                    _LOGGER.debug("Set preset mode: %s", preset_mode)
                    try:
                        await self.coordinator.data.update_thermostat(
                            location, device, thermostatSetpointStatus=preset_mode
                        )
                    except LYRIC_EXCEPTIONS as exception:
                        _LOGGER.error(exception)
        await self.coordinator.async_refresh()

    async def async_set_preset_period(self, period: str) -> None:
        """Set preset period (time)."""
        for location in self.coordinator.data.locations:
            for device in location.devices:
                if device.macID == self._device.macID:
                    try:
                        await self.coordinator.data.update_thermostat(
                            location, device, nextPeriodTime=period
                        )
                    except LYRIC_EXCEPTIONS as exception:
                        _LOGGER.error(exception)
        await self.coordinator.async_refresh()

    async def set_hold_time(self, time: str) -> None:
        """Set the time to hold until."""
        _LOGGER.debug("set_hold_time: %s", time)

        for location in self.coordinator.data.locations:
            for device in location.devices:
                if device.macID == self._device.macID:
                    try:
                        await self.coordinator.data.update_thermostat(
                            location,
                            device,
                            thermostatSetpointStatus=PRESET_HOLD_UNTIL,
                            nextPeriodTime=time,
                        )
                    except LYRIC_EXCEPTIONS as exception:
                        _LOGGER.error(exception)
        await self.coordinator.async_refresh()
