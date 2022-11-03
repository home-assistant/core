"""Python Control of Nobø Hub - Nobø Energy Control."""
from __future__ import annotations

from typing import Any

from pynobo import nobo

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MODE,
    ATTR_NAME,
    ATTR_SUGGESTED_AREA,
    ATTR_VIA_DEVICE,
    PRECISION_TENTHS,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_OVERRIDE_ALLOWED,
    ATTR_SERIAL,
    ATTR_TARGET_ID,
    ATTR_TARGET_TYPE,
    ATTR_TEMP_COMFORT_C,
    ATTR_TEMP_ECO_C,
    CONF_OVERRIDE_TYPE,
    DOMAIN,
    OVERRIDE_TYPE_NOW,
)

SUPPORT_FLAGS = (
    ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
)

PRESET_MODES = [PRESET_NONE, PRESET_COMFORT, PRESET_ECO, PRESET_AWAY]

MIN_TEMPERATURE = 7
MAX_TEMPERATURE = 40


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Nobø Ecohub platform from UI configuration."""

    # Setup connection with hub
    hub: nobo = hass.data[DOMAIN][config_entry.entry_id]

    override_type = (
        nobo.API.OVERRIDE_TYPE_NOW
        if config_entry.options.get(CONF_OVERRIDE_TYPE) == OVERRIDE_TYPE_NOW
        else nobo.API.OVERRIDE_TYPE_CONSTANT
    )

    # Add zones as entities
    async_add_entities(NoboZone(zone_id, hub, override_type) for zone_id in hub.zones)


class NoboZone(ClimateEntity):
    """Representation of a Nobø zone.

    A Nobø zone consists of a group of physical devices that are
    controlled as a unity.
    """

    _attr_max_temp = MAX_TEMPERATURE
    _attr_min_temp = MIN_TEMPERATURE
    _attr_precision = PRECISION_TENTHS
    _attr_preset_modes = PRESET_MODES
    _attr_supported_features = SUPPORT_FLAGS
    _attr_temperature_unit = TEMP_CELSIUS
    _attr_target_temperature_step = 1
    # Need to poll to get preset change when in HVACMode.AUTO, so can't set _attr_should_poll = False

    def __init__(self, zone_id, hub: nobo, override_type):
        """Initialize the climate device."""
        self._id = zone_id
        self._nobo = hub
        self._attr_unique_id = f"{hub.hub_serial}:{zone_id}"
        self._attr_name = None
        self._attr_has_entity_name = True
        self._attr_hvac_mode = HVACMode.AUTO
        self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.AUTO]
        self._override_type = override_type
        self._attr_device_info: DeviceInfo = {
            ATTR_IDENTIFIERS: {(DOMAIN, f"{hub.hub_serial}:{zone_id}")},
            ATTR_NAME: hub.zones[zone_id][ATTR_NAME],
            ATTR_VIA_DEVICE: (DOMAIN, hub.hub_info[ATTR_SERIAL]),
            ATTR_SUGGESTED_AREA: hub.zones[zone_id][ATTR_NAME],
        }
        self._read_state()

    async def async_added_to_hass(self) -> None:
        """Register callback from hub."""
        self._nobo.register_callback(self._after_update)

    async def async_will_remove_from_hass(self) -> None:
        """Deregister callback from hub."""
        self._nobo.deregister_callback(self._after_update)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target HVAC mode, if it's supported."""
        if hvac_mode not in self.hvac_modes:
            raise ValueError(
                f"Zone {self._id} '{self._attr_name}' called with unsupported HVAC mode '{hvac_mode}'"
            )
        if hvac_mode == HVACMode.AUTO:
            await self.async_set_preset_mode(PRESET_NONE)
        elif hvac_mode == HVACMode.HEAT:
            await self.async_set_preset_mode(PRESET_COMFORT)
        self._attr_hvac_mode = hvac_mode

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
        if ATTR_TARGET_TEMP_LOW in kwargs:
            low = round(kwargs[ATTR_TARGET_TEMP_LOW])
            high = round(kwargs[ATTR_TARGET_TEMP_HIGH])
            low = min(low, high)
            high = max(low, high)
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
        self.async_write_ha_state()
