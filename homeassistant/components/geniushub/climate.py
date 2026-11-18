"""Support for Genius Hub climate devices."""

from typing import override

from homeassistant.components.climate import (
    PRESET_ACTIVITY,
    PRESET_BOOST,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GeniusHubConfigEntry
from .const import (
    GH_HVAC_TO_HA,
    GH_PRESET_TO_HA,
    GH_TYPE,
    GH_ZONES,
    HA_HVAC_TO_GH,
    HA_PRESET_TO_GH,
)
from .coordinator import GeniusCoordinator
from .entity import GeniusHeatingZone


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GeniusHubConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Genius Hub climate entities."""

    coordinator: GeniusCoordinator = entry.runtime_data

    async_add_entities(
        GeniusClimateZone(coordinator, z)
        for z in coordinator.client.zone_objs
        if z.data.get(GH_TYPE) in GH_ZONES
    )


class GeniusClimateZone(GeniusHeatingZone, ClimateEntity):
    """Representation of a Genius Hub climate device."""

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )

    def __init__(self, coordinator: GeniusCoordinator, zone) -> None:
        """Initialize the climate device."""
        super().__init__(coordinator, zone)

        self._max_temp = 28.0
        self._min_temp = 4.0

    @property
    @override
    def icon(self) -> str:
        """Return the icon to use in the frontend UI."""
        return "mdi:radiator"

    @property
    @override
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        return GH_HVAC_TO_HA.get(self._zone.data["mode"], HVACMode.AUTO)

    @property
    @override
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes."""
        return list(HA_HVAC_TO_GH)

    @property
    @override
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation if supported."""
        if "_state" in self._zone.data:  # only for v3 API
            if self._zone.data["mode"] == "off":
                return HVACAction.OFF
            if self._zone.data["output"] == 1:
                return HVACAction.HEATING
            return HVACAction.IDLE

        return None

    @property
    @override
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        return GH_PRESET_TO_HA.get(self._zone.data["mode"])

    @property
    @override
    def preset_modes(self) -> list[str] | None:
        """Return a list of available preset modes."""
        if "occupied" in self._zone.data:  # if has a movement sensor
            return [PRESET_ACTIVITY, PRESET_BOOST]
        return [PRESET_BOOST]

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set a new hvac mode."""
        await self._zone.set_mode(HA_HVAC_TO_GH.get(hvac_mode))

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set a new preset mode."""
        await self._zone.set_mode(HA_PRESET_TO_GH.get(preset_mode, "timer"))
