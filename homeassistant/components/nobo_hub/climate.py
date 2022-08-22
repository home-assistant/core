"""Python Control of Nobø Hub - Nobø Energy Control."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from pynobo import nobo
import voluptuous as vol

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_MODE,
    ATTR_NAME,
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    PRECISION_TENTHS,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_OVERRIDE_ALLOWED,
    ATTR_TARGET_ID,
    ATTR_TARGET_TYPE,
    ATTR_TEMP_COMFORT_C,
    ATTR_TEMP_ECO_C,
    CONF_OVERRIDE_TYPE,
    CONF_OVERRIDE_TYPE_NOW,
    DOMAIN,
)

SUPPORT_FLAGS = (
    ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
)

PRESET_MODES = [PRESET_NONE, PRESET_COMFORT, PRESET_ECO, PRESET_AWAY]

MIN_TEMPERATURE = 7
MAX_TEMPERATURE = 40

_LOGGER = logging.getLogger(__name__)

_ZONE_NORMAL_WEEK_LIST_SCHEMA = vol.Schema({cv.string: cv.string})


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Nobø Ecohub platform from UI configuration."""

    # Setup connection with hub
    hub = hass.data[DOMAIN][config_entry.entry_id].hub

    override_type = (
        nobo.API.OVERRIDE_TYPE_NOW
        if config_entry.options.get(CONF_OVERRIDE_TYPE) == CONF_OVERRIDE_TYPE_NOW
        else nobo.API.OVERRIDE_TYPE_CONSTANT
    )

    # Find OFF command (week profile) to use for all zones:
    command_off_name = config_entry.options.get(CONF_COMMAND_OFF)
    command_on_by_id: dict[str, str] = {}  # By default, nothing can be turned on
    if not command_off_name:
        _LOGGER.debug(
            "Not possible to turn off (or on) any zone, because OFF week profile was not specified"
        )
        command_off_id = None
    else:
        command_off_id = _get_id_from_name(command_off_name, hub.week_profiles)
        if not command_off_id:
            _LOGGER.warning(
                "Can not turn off (or on) any zone, because week profile '%s' was not found",
                command_off_name,
            )
        else:
            _LOGGER.debug(
                "To turn off any heater, week profile %s '%s' will be used",
                command_off_id,
                command_off_name,
            )

            # Find ON command (week profile) for the different zones:
            command_on_dict = config_entry.options.get(CONF_COMMAND_ON)
            if not command_on_dict:
                _LOGGER.warning(
                    "Not possible to turn on any zone, because ON week profile was not specified"
                )
            else:
                _set_on_commands(command_on_by_id, command_on_dict, hub)

    # Add zones as entities
    async_add_entities(
        (
            NoboZone(
                zone_id,
                hub,
                command_off_id,
                command_on_by_id.get(zone_id),
                override_type,
            )
            for zone_id in hub.zones
        ),
        True,
    )


def _set_on_commands(command_on_by_id, command_on_dict, hub):
    for zone_id, zone in hub.zones.items():
        # Replace unicode non-breaking space (used in Nobø Ecohub) with space
        zone_name = zone[ATTR_NAME].replace("\xa0", " ")
        if zone_name not in command_on_dict:
            continue
        command_on_name = command_on_dict[zone_name]
        if not command_on_name:
            _LOGGER.warning(
                "Can not turn on (or off) zone '%s', because ON week profile was not specified",
                zone_name,
            )
            continue
        command_on_id = _get_id_from_name(command_on_name, hub.week_profiles)
        if not command_on_id:
            _LOGGER.warning(
                "Can not turn on (or off) zone '%s', because ON week profile '%s' was not found",
                zone_name,
                command_on_name,
            )
        else:
            _LOGGER.debug(
                "To turn on heater %s '%s', week profile %s '%s' will be used",
                zone_id,
                zone_name,
                command_on_id,
                command_on_name,
            )
            command_on_by_id[zone_id] = command_on_id


def _get_id_from_name(name, dictionary):
    for key in dictionary.keys():
        # Replace unicode non-breaking space (used in Nobø Ecohub) with space
        if dictionary[key][ATTR_NAME].replace("\xa0", " ") == name:
            return key
    return None


class NoboZone(ClimateEntity):
    """Representation of a Nobø zone.

    A Nobø zone consists of a group of physical devices that are
    controlled as a unity.
    """

    _attr_max_temp = MAX_TEMPERATURE
    _attr_min_temp = MIN_TEMPERATURE
    _attr_precision = PRECISION_TENTHS
    _attr_preset_modes = PRESET_MODES
    # Need to poll to get preset change when in HVACMode.AUTO.
    _attr_should_poll = True
    _attr_supported_features = SUPPORT_FLAGS
    _attr_temperature_unit = TEMP_CELSIUS

    def __init__(
        self, zone_id, hub: nobo, command_off_id, command_on_id, override_type
    ):
        """Initialize the climate device."""
        self._id = zone_id
        self._nobo = hub
        self._attr_unique_id = hub.hub_serial + ":" + zone_id
        self._attr_name = hub.zones[self._id][ATTR_NAME]
        self._attr_hvac_mode = HVACMode.AUTO
        self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.AUTO]
        self._command_off_id = command_off_id
        self._command_on_id = command_on_id

        # Only enable HVACMode.OFF if on- and off-command exists for this zone:
        if self._command_on_id is not None and self._command_off_id is not None:
            self._attr_hvac_modes.append(HVACMode.OFF)
        self._override_type = override_type

    async def async_added_to_hass(self) -> None:
        """Register callback from hub."""
        self._nobo.register_callback(self._after_update)

    async def async_will_remove_from_hass(self) -> None:
        """Deregister callback from hub."""
        self._nobo.deregister_callback(self._after_update)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target HVAC mode, if it's supported."""
        if hvac_mode not in self.hvac_modes:
            _LOGGER.warning(
                "Zone %s '%s' called with unsupported HVAC mode '%s'",
                self._id,
                self._attr_name,
                hvac_mode,
            )
            return
        if hvac_mode == HVACMode.OFF:
            await self.async_set_preset_mode(PRESET_NONE)
            # Turn off by switching to configured "off" profile
            await self._switch_profile(self._command_off_id)
        else:
            if hvac_mode == HVACMode.AUTO:
                await self.async_set_preset_mode(PRESET_NONE)
            elif hvac_mode == HVACMode.HEAT:
                await self.async_set_preset_mode(PRESET_COMFORT)
            if self._attr_hvac_mode == HVACMode.OFF:
                # Turn on by switching to configured "on" profile
                await self._switch_profile(self._command_on_id)
        self._attr_hvac_mode = hvac_mode

    async def _switch_profile(self, week_profile_id):
        """Switch week profile. Used to switch heaters on and off."""
        await self._nobo.async_update_zone(self._id, week_profile_id=week_profile_id)
        _LOGGER.debug(
            "Turned %s heater %s '%s' by switching to week profile %s",
            "off" if week_profile_id == self._command_off_id else "on",
            self._id,
            self._attr_name,
            self._command_off_id,
        )
        # When switching between AUTO and OFF an immediate update does not work (the Nobø API seems to answer with old values), but it works if we add a short delay:
        await asyncio.sleep(0.5)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new zone override."""
        if self._nobo.zones[self._id][ATTR_OVERRIDE_ALLOWED] != "1":
            return
        if preset_mode == PRESET_ECO:
            mode = nobo.API.OVERRIDE_MODE_ECO
        elif preset_mode == PRESET_AWAY:
            mode = nobo.API.OVERRIDE_MODE_AWAY
        elif preset_mode == PRESET_COMFORT:
            mode = nobo.API.OVERRIDE_MODE_COMFORT
        else:  # PRESET_NONE
            mode = nobo.API.OVERRIDE_MODE_NORMAL
        await self._nobo.async_create_override(
            mode,
            self._override_type,
            nobo.API.OVERRIDE_TARGET_ZONE,
            self._id,
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        low, high = None, None
        if ATTR_TARGET_TEMP_LOW in kwargs:
            low = int(kwargs.get(ATTR_TARGET_TEMP_LOW))  # type: ignore[arg-type]  # ATTR_TARGET_TEMP_LOW is float if set
        if ATTR_TARGET_TEMP_HIGH in kwargs:
            high = int(kwargs.get(ATTR_TARGET_TEMP_HIGH))  # type: ignore[arg-type]  # ATTR_TARGET_TEMP_HIGH is float if set
        if low is not None:
            if high is not None:
                low = min(low, high)
            elif self.target_temperature_high is not None:
                low = min(low, int(self.target_temperature_high))
        elif high is not None and self.target_temperature_low is not None:
            high = max(high, int(self.target_temperature_low))
        await self._nobo.async_update_zone(
            self._id, temp_comfort_c=high, temp_eco_c=low
        )

    async def async_update(self) -> None:
        """Fetch new state data for this zone."""
        self._read_state()

    @callback
    def _read_state(self) -> None:
        """Read the current state from the hub. These are only local calls."""
        state = self._nobo.get_current_zone_mode(self._id)
        self._attr_hvac_mode = HVACMode.AUTO
        self._attr_preset_mode = PRESET_NONE

        if state == nobo.API.NAME_OFF:
            self._attr_hvac_mode = HVACMode.OFF
        elif state == nobo.API.NAME_AWAY:
            self._attr_preset_mode = PRESET_AWAY
        elif state == nobo.API.NAME_ECO:
            self._attr_preset_mode = PRESET_ECO
        elif state == nobo.API.NAME_COMFORT:
            self._attr_preset_mode = PRESET_COMFORT

        if self._nobo.zones[self._id][ATTR_OVERRIDE_ALLOWED] == "1":
            for override in self._nobo.overrides:
                if self._nobo.overrides[override][ATTR_MODE] == "0":
                    continue  # "normal" overrides
                if (
                    self._nobo.overrides[override][ATTR_TARGET_TYPE]
                    == nobo.API.OVERRIDE_TARGET_ZONE
                    and self._nobo.overrides[override][ATTR_TARGET_ID] == self._id
                ):
                    self._attr_hvac_mode = HVACMode.HEAT
                    break

        current_temperature = self._nobo.get_current_zone_temperature(self._id)
        self._attr_current_temperature = (
            None if current_temperature is None else float(current_temperature)
        )
        self._attr_target_temperature_high = int(
            self._nobo.zones[self._id][ATTR_TEMP_COMFORT_C]
        )
        self._attr_target_temperature_low = int(
            self._nobo.zones[self._id][ATTR_TEMP_ECO_C]
        )

    @callback
    def _after_update(self, hub):
        self._read_state()
        self.async_schedule_update_ha_state()
