"""Support for Daikin AirBase zones."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN as DAIKIN_DOMAIN, DaikinApi

ZONE_ICON = "mdi:home-circle"
STREAMER_ICON = "mdi:air-filter"
DAIKIN_ATTR_ADVANCED = "adv"
DAIKIN_ATTR_STREAMER = "streamer"


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Old way of setting up the platform.

    Can only be called when a user accidentally mentions the platform in their
    config. But even in that case it would have been ignored.
    """


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Daikin climate based on config_entry."""
    daikin_api: DaikinApi = hass.data[DAIKIN_DOMAIN][entry.entry_id]
    switches: list[DaikinZoneSwitch | DaikinStreamerSwitch] = []
    if zones := daikin_api.device.zones:
        switches.extend(
            [
                DaikinZoneSwitch(daikin_api, zone_id)
                for zone_id, zone in enumerate(zones)
                if zone != ("-", "0")
            ]
        )
    if daikin_api.device.support_advanced_modes:
        # It isn't possible to find out from the API responses if a specific
        # device supports the streamer, so assume so if it does support
        # advanced modes.
        switches.append(DaikinStreamerSwitch(daikin_api))
    if switches:
        async_add_entities(switches)


class DaikinZoneSwitch(SwitchEntity):
    """Representation of a zone."""

    def __init__(self, daikin_api: DaikinApi, zone_id):
        """Initialize the zone."""
        self._api = daikin_api
        self._zone_id = zone_id

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._api.device.mac}-zone{self._zone_id}"

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ZONE_ICON

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._api.name} {self._api.device.zones[self._zone_id][0]}"

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self._api.device.zones[self._zone_id][1] == "1"

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return self._api.device_info

    async def async_update(self) -> None:
        """Retrieve latest state."""
        await self._api.async_update()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the zone on."""
        await self._api.device.set_zone(self._zone_id, "1")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the zone off."""
        await self._api.device.set_zone(self._zone_id, "0")


class DaikinStreamerSwitch(SwitchEntity):
    """Streamer state."""

    def __init__(self, daikin_api: DaikinApi) -> None:
        """Initialize streamer switch."""
        self._api = daikin_api

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._api.device.mac}-streamer"

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return STREAMER_ICON

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._api.name} streamer"

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return (
            DAIKIN_ATTR_STREAMER in self._api.device.represent(DAIKIN_ATTR_ADVANCED)[1]
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return self._api.device_info

    async def async_update(self) -> None:
        """Retrieve latest state."""
        await self._api.async_update()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the zone on."""
        await self._api.device.set_streamer("on")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the zone off."""
        await self._api.device.set_streamer("off")
