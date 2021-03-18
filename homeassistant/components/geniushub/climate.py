"""Support for Genius Hub climate devices."""
from __future__ import annotations

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_ACTIVITY,
    PRESET_BOOST,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from . import DOMAIN, GeniusHeatingZone

# GeniusHub Zones support: Off, Timer, Override/Boost, Footprint & Linked modes
HA_HVAC_TO_GH = {HVAC_MODE_OFF: "off", HVAC_MODE_HEAT: "timer"}
GH_HVAC_TO_HA = {v: k for k, v in HA_HVAC_TO_GH.items()}

HA_PRESET_TO_GH = {PRESET_ACTIVITY: "footprint", PRESET_BOOST: "override"}
GH_PRESET_TO_HA = {v: k for k, v in HA_PRESET_TO_GH.items()}

GH_ZONES = ["radiator", "wet underfloor"]


async def async_setup_platform(
    hass: HomeAssistantType, config: ConfigType, async_add_entities, discovery_info=None
) -> None:
    """Set up the Genius Hub climate entities."""
    if discovery_info is None:
        return

    broker = hass.data[DOMAIN]["broker"]

    async_add_entities(
        [
            GeniusClimateZone(broker, z)
            for z in broker.client.zone_objs
            if z.data["type"] in GH_ZONES
        ]
    )


class GeniusClimateZone(GeniusHeatingZone, ClimateEntity):
    """Representation of a Genius Hub climate device."""

    def __init__(self, broker, zone) -> None:
        """Initialize the climate device."""
        super().__init__(broker, zone)

        self._max_temp = 28.0
        self._min_temp = 4.0
        self._supported_features = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend UI."""
        return "mdi:radiator"

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode."""
        return GH_HVAC_TO_HA.get(self._zone.data["mode"], HVAC_MODE_HEAT)

    @property
    def hvac_modes(self) -> list[str]:
        """Return the list of available hvac operation modes."""
        return list(HA_HVAC_TO_GH)

    @property
    def hvac_action(self) -> str | None:
        """Return the current running hvac operation if supported."""
        if "_state" in self._zone.data:  # only for v3 API
            if not self._zone.data["_state"].get("bIsActive"):
                return CURRENT_HVAC_OFF
            if self._zone.data["_state"].get("bOutRequestHeat"):
                return CURRENT_HVAC_HEAT
            return CURRENT_HVAC_IDLE
        return None

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        return GH_PRESET_TO_HA.get(self._zone.data["mode"])

    @property
    def preset_modes(self) -> list[str] | None:
        """Return a list of available preset modes."""
        if "occupied" in self._zone.data:  # if has a movement sensor
            return [PRESET_ACTIVITY, PRESET_BOOST]
        return [PRESET_BOOST]

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set a new hvac mode."""
        await self._zone.set_mode(HA_HVAC_TO_GH.get(hvac_mode))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set a new preset mode."""
        await self._zone.set_mode(HA_PRESET_TO_GH.get(preset_mode, "timer"))
