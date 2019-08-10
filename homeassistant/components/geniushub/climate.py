"""Support for Genius Hub climate devices."""
import logging
from typing import Any, Awaitable, Dict, Optional, List

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    HVAC_MODE_OFF,
    HVAC_MODE_HEAT,
    PRESET_BOOST,
    PRESET_ACTIVITY,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_PRESET_MODE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_DURATION = "duration"

GH_ZONES = ["radiator"]

# temperature is repeated here, as it gives access to high-precision temps
GH_STATE_ATTRS = ["mode", "temperature", "type", "occupied", "override"]

# GeniusHub Zones support: Off, Timer, Override/Boost, Footprint & Linked modes
HA_HVAC_TO_GH = {HVAC_MODE_OFF: "off", HVAC_MODE_HEAT: "timer"}
GH_HVAC_TO_HA = {v: k for k, v in HA_HVAC_TO_GH.items()}

HA_PRESET_TO_GH = {PRESET_ACTIVITY: "footprint", PRESET_BOOST: "override"}
GH_PRESET_TO_HA = {v: k for k, v in HA_PRESET_TO_GH.items()}


async def async_setup_platform(
    hass, hass_config, async_add_entities, discovery_info=None
):
    """Set up the Genius Hub climate entities."""
    client = hass.data[DOMAIN]["client"]

    async_add_entities(
        [
            GeniusClimateZone(client, z)
            for z in client.hub.zone_objs
            if z.type in GH_ZONES
        ]
    )


class GeniusClimateZone(ClimateDevice):
    """Representation of a Genius Hub climate device."""

    def __init__(self, client, zone):
        """Initialize the climate device."""
        self._client = client
        self._zone = zone

        if hasattr(self._zone, "occupied"):  # has a movement sensor
            self._preset_modes = list(HA_PRESET_TO_GH)
        else:
            self._preset_modes = [PRESET_BOOST]

    async def async_added_to_hass(self) -> Awaitable[None]:
        """Run when entity about to be added."""
        async_dispatcher_connect(self.hass, DOMAIN, self._refresh)

    @callback
    def _refresh(self) -> None:
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def name(self) -> str:
        """Return the name of the climate device."""
        return self._zone.name

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the device state attributes."""
        tmp = self._zone.__dict__.items()
        return {"status": {k: v for k, v in tmp if k in GH_STATE_ATTRS}}

    @property
    def should_poll(self) -> bool:
        """Return False as the geniushub devices should not be polled."""
        return False

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend UI."""
        return "mdi:radiator"

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        return self._zone.temperature

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the temperature we try to reach."""
        return self._zone.setpoint

    @property
    def min_temp(self) -> float:
        """Return max valid temperature that can be set."""
        return 4.0

    @property
    def max_temp(self) -> float:
        """Return max valid temperature that can be set."""
        return 28.0

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode."""
        return GH_HVAC_TO_HA.get(self._zone.mode, HVAC_MODE_HEAT)

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes."""
        return list(HA_HVAC_TO_GH)

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., home, away, temp."""
        return GH_PRESET_TO_HA.get(self._zone.mode)

    @property
    def preset_modes(self) -> Optional[List[str]]:
        """Return a list of available preset modes."""
        return self._preset_modes

    async def async_set_temperature(self, **kwargs) -> Awaitable[None]:
        """Set a new target temperature for this zone."""
        await self._zone.set_override(
            kwargs[ATTR_TEMPERATURE], kwargs.get(ATTR_DURATION, 3600)
        )

    async def async_set_hvac_mode(self, hvac_mode: str) -> Awaitable[None]:
        """Set a new hvac mode."""
        await self._zone.set_mode(HA_HVAC_TO_GH.get(hvac_mode))

    async def async_set_preset_mode(self, preset_mode: str) -> Awaitable[None]:
        """Set a new preset mode."""
        await self._zone.set_mode(HA_PRESET_TO_GH.get(preset_mode, "timer"))
