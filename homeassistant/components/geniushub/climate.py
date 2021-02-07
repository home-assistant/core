"""Support for Genius Hub climate devices."""
from datetime import timedelta
from typing import List, Optional

import voluptuous as vol

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
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from . import DOMAIN, GeniusHeatingZone

# GeniusHub Zones support: Off, Timer, Override/Boost, Footprint & Linked modes
HA_HVAC_TO_GH = {HVAC_MODE_OFF: "off", HVAC_MODE_HEAT: "timer"}
GH_HVAC_TO_HA = {v: k for k, v in HA_HVAC_TO_GH.items()}

HA_PRESET_TO_GH = {PRESET_ACTIVITY: "footprint", PRESET_BOOST: "override"}
GH_PRESET_TO_HA = {v: k for k, v in HA_PRESET_TO_GH.items()}

GH_ZONES = ["radiator", "wet underfloor"]

ATTR_ZONE_MODE = "mode"
ATTR_DURATION = "duration"

SVC_SET_ZONE_MODE = "set_zone_mode"
SVC_SET_ZONE_OVERRIDE = "set_zone_override"

SET_ZONE_MODE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_ZONE_MODE): vol.In(["off", "timer", "footprint"]),
    }
)
SET_ZONE_OVERRIDE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_TEMPERATURE): vol.All(
            vol.Coerce(float), vol.Range(min=4, max=28)
        ),
        vol.Optional(ATTR_DURATION): vol.All(
            cv.time_period,
            vol.Range(min=timedelta(minutes=5), max=timedelta(days=1)),
        ),
    }
)


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

    # Register custom services
    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SVC_SET_ZONE_MODE,
        SET_ZONE_MODE_SCHEMA,
        "async_set_zone",
    )

    platform.async_register_entity_service(
        SVC_SET_ZONE_OVERRIDE,
        SET_ZONE_OVERRIDE_SCHEMA,
        "async_set_temperature",
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
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes."""
        return list(HA_HVAC_TO_GH)

    @property
    def hvac_action(self) -> Optional[str]:
        """Return the current running hvac operation if supported."""
        if "_state" in self._zone.data:  # only for v3 API
            if not self._zone.data["_state"].get("bIsActive"):
                return CURRENT_HVAC_OFF
            if self._zone.data["_state"].get("bOutRequestHeat"):
                return CURRENT_HVAC_HEAT
            return CURRENT_HVAC_IDLE
        return None

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., home, away, temp."""
        return GH_PRESET_TO_HA.get(self._zone.data["mode"])

    @property
    def preset_modes(self) -> Optional[List[str]]:
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

    async def async_set_zone(self, **kwargs) -> None:
        """Set a new mode for this zone."""
        mode = kwargs.get(ATTR_ZONE_MODE)

        if mode == "footprint" and not self._zone._has_pir:
            raise TypeError(
                f"'{self.entity_id}' can not support footprint mode (it has no PIR)"
            )
        await self._zone.set_mode(mode)

    async def async_set_temperature(self, **kwargs) -> None:
        """Set a new target temperature for and options duration this zone."""
        await self._zone.set_override(kwargs[ATTR_TEMPERATURE], int(kwargs.get(ATTR_DURATION, 3600).total_seconds()))
