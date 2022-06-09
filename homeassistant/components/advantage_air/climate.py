"""Climate platform for Advantage Air integration."""
from __future__ import annotations

import logging

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ADVANTAGE_AIR_STATE_CLOSE,
    ADVANTAGE_AIR_STATE_OFF,
    ADVANTAGE_AIR_STATE_ON,
    ADVANTAGE_AIR_STATE_OPEN,
    DOMAIN as ADVANTAGE_AIR_DOMAIN,
)
from .entity import AdvantageAirEntity

ADVANTAGE_AIR_HVAC_MODES = {
    "heat": HVACMode.HEAT,
    "cool": HVACMode.COOL,
    "vent": HVACMode.FAN_ONLY,
    "dry": HVACMode.DRY,
    "myauto": HVACMode.AUTO,
}
HASS_HVAC_MODES = {v: k for k, v in ADVANTAGE_AIR_HVAC_MODES.items()}

AC_HVAC_MODES = [
    HVACMode.OFF,
    HVACMode.COOL,
    HVACMode.HEAT,
    HVACMode.FAN_ONLY,
    HVACMode.DRY,
]

ADVANTAGE_AIR_FAN_MODES = {
    "auto": FAN_AUTO,
    "low": FAN_LOW,
    "medium": FAN_MEDIUM,
    "high": FAN_HIGH,
}
HASS_FAN_MODES = {v: k for k, v in ADVANTAGE_AIR_FAN_MODES.items()}
FAN_SPEEDS = {FAN_LOW: 30, FAN_MEDIUM: 60, FAN_HIGH: 100}

ADVANTAGE_AIR_SERVICE_SET_MYZONE = "set_myzone"
ZONE_HVAC_MODES = [HVACMode.OFF, HVACMode.HEAT_COOL]

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AdvantageAir climate platform."""

    instance = hass.data[ADVANTAGE_AIR_DOMAIN][config_entry.entry_id]

    entities: list[ClimateEntity] = []
    for ac_key, ac_device in instance["coordinator"].data["aircons"].items():
        entities.append(AdvantageAirAC(instance, ac_key))
        for zone_key, zone in ac_device["zones"].items():
            # Only add zone climate control when zone is in temperature control
            if zone["type"] != 0:
                entities.append(AdvantageAirZone(instance, ac_key, zone_key))
    async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        ADVANTAGE_AIR_SERVICE_SET_MYZONE,
        {},
        "set_myzone",
    )


class AdvantageAirClimateEntity(AdvantageAirEntity, ClimateEntity):
    """AdvantageAir Climate class."""

    _attr_temperature_unit = TEMP_CELSIUS
    _attr_target_temperature_step = PRECISION_WHOLE
    _attr_max_temp = 32
    _attr_min_temp = 16


class AdvantageAirAC(AdvantageAirClimateEntity):
    """AdvantageAir AC unit."""

    _attr_fan_modes = [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]
    _attr_hvac_modes = AC_HVAC_MODES
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
    )

    def __init__(self, instance, ac_key):
        """Initialize an AdvantageAir AC unit."""
        super().__init__(instance, ac_key)
        self._attr_name = self._ac["name"]
        self._attr_unique_id = f'{self.coordinator.data["system"]["rid"]}-{ac_key}'
        if self._ac.get("myAutoModeEnabled"):
            self._attr_hvac_modes = AC_HVAC_MODES + [HVACMode.AUTO]

    @property
    def target_temperature(self):
        """Return the current target temperature."""
        return self._ac["setTemp"]

    @property
    def hvac_mode(self):
        """Return the current HVAC modes."""
        if self._ac["state"] == ADVANTAGE_AIR_STATE_ON:
            return ADVANTAGE_AIR_HVAC_MODES.get(self._ac["mode"])
        return HVACMode.OFF

    @property
    def fan_mode(self):
        """Return the current fan modes."""
        return ADVANTAGE_AIR_FAN_MODES.get(self._ac["fan"])

    async def async_set_hvac_mode(self, hvac_mode):
        """Set the HVAC Mode and State."""
        if hvac_mode == HVACMode.OFF:
            await self.async_change(
                {self.ac_key: {"info": {"state": ADVANTAGE_AIR_STATE_OFF}}}
            )
        else:
            await self.async_change(
                {
                    self.ac_key: {
                        "info": {
                            "state": ADVANTAGE_AIR_STATE_ON,
                            "mode": HASS_HVAC_MODES.get(hvac_mode),
                        }
                    }
                }
            )

    async def async_set_fan_mode(self, fan_mode):
        """Set the Fan Mode."""
        await self.async_change(
            {self.ac_key: {"info": {"fan": HASS_FAN_MODES.get(fan_mode)}}}
        )

    async def async_set_temperature(self, **kwargs):
        """Set the Temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        await self.async_change({self.ac_key: {"info": {"setTemp": temp}}})


class AdvantageAirZone(AdvantageAirClimateEntity):
    """AdvantageAir Zone control."""

    _attr_hvac_modes = ZONE_HVAC_MODES
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(self, instance, ac_key, zone_key):
        """Initialize an AdvantageAir Zone control."""
        super().__init__(instance, ac_key, zone_key)
        self._attr_name = self._zone["name"]
        self._attr_unique_id = (
            f'{self.coordinator.data["system"]["rid"]}-{ac_key}-{zone_key}'
        )

    @property
    def hvac_mode(self):
        """Return the current state as HVAC mode."""
        if self._zone["state"] == ADVANTAGE_AIR_STATE_OPEN:
            return HVACMode.HEAT_COOL
        return HVACMode.OFF

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._zone["measuredTemp"]

    @property
    def target_temperature(self):
        """Return the target temperature."""
        return self._zone["setTemp"]

    async def async_set_hvac_mode(self, hvac_mode):
        """Set the HVAC Mode and State."""
        if hvac_mode == HVACMode.OFF:
            await self.async_change(
                {
                    self.ac_key: {
                        "zones": {self.zone_key: {"state": ADVANTAGE_AIR_STATE_CLOSE}}
                    }
                }
            )
        else:
            await self.async_change(
                {
                    self.ac_key: {
                        "zones": {self.zone_key: {"state": ADVANTAGE_AIR_STATE_OPEN}}
                    }
                }
            )

    async def async_set_temperature(self, **kwargs):
        """Set the Temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        await self.async_change(
            {self.ac_key: {"zones": {self.zone_key: {"setTemp": temp}}}}
        )

    async def set_myzone(self, **kwargs):
        """Set this zone as the 'MyZone'."""
        _LOGGER.warning(
            "The advantage_air.set_myzone service has been deprecated and will be removed in a future version, please use the select.select_option service on the MyZone entity"
        )
        await self.async_change(
            {self.ac_key: {"info": {"myZone": self._zone["number"]}}}
        )
