"""Support for Daikin AirBase zones."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .coordinator import DaikinCoordinator
from .entity import DaikinEntity

DAIKIN_ATTR_ADVANCED = "adv"
DAIKIN_ATTR_STREAMER = "streamer"
DAIKIN_ATTR_MODE = "mode"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Daikin climate based on config_entry."""
    daikin_api: DaikinCoordinator = hass.data[DOMAIN][entry.entry_id]
    switches: list[SwitchEntity] = []
    if zones := daikin_api.device.zones:
        switches.extend(
            DaikinZoneSwitch(daikin_api, zone_id)
            for zone_id, zone in enumerate(zones)
            if zone[0] != "-"
        )
    if daikin_api.device.support_advanced_modes:
        # It isn't possible to find out from the API responses if a specific
        # device supports the streamer, so assume so if it does support
        # advanced modes.
        switches.append(DaikinStreamerSwitch(daikin_api))
    switches.append(DaikinToggleSwitch(daikin_api))
    async_add_entities(switches)


class DaikinZoneSwitch(DaikinEntity, SwitchEntity):
    """Representation of a zone."""

    _attr_translation_key = "zone"

    def __init__(self, coordinator: DaikinCoordinator, zone_id: int) -> None:
        """Initialize the zone."""
        super().__init__(coordinator)
        self._zone_id = zone_id
        self._attr_unique_id = f"{self.device.mac}-zone{zone_id}"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self.device.zones[self._zone_id][0]

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self.device.zones[self._zone_id][1] == "1"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the zone on."""
        await self.device.set_zone(self._zone_id, "zone_onoff", "1")
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the zone off."""
        await self.device.set_zone(self._zone_id, "zone_onoff", "0")
        await self.coordinator.async_refresh()


class DaikinStreamerSwitch(DaikinEntity, SwitchEntity):
    """Streamer state."""

    _attr_name = "Streamer"
    _attr_translation_key = "streamer"

    def __init__(self, coordinator: DaikinCoordinator) -> None:
        """Initialize switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.device.mac}-streamer"

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return DAIKIN_ATTR_STREAMER in self.device.represent(DAIKIN_ATTR_ADVANCED)[1]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the zone on."""
        await self.device.set_streamer("on")
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the zone off."""
        await self.device.set_streamer("off")
        await self.coordinator.async_refresh()


class DaikinToggleSwitch(DaikinEntity, SwitchEntity):
    """Switch state."""

    _attr_translation_key = "toggle"

    def __init__(self, coordinator: DaikinCoordinator) -> None:
        """Initialize switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.device.mac}-toggle"

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return "off" not in self.device.represent(DAIKIN_ATTR_MODE)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the zone on."""
        await self.device.set({})
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the zone off."""
        await self.device.set({DAIKIN_ATTR_MODE: "off"})
        await self.coordinator.async_refresh()
