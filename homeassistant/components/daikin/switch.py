"""Support for Daikin AirBase zones."""
import logging

from homeassistant.helpers.entity import ToggleEntity

from . import DOMAIN as DAIKIN_DOMAIN

_LOGGER = logging.getLogger(__name__)

ZONE_ICON = "mdi:home-circle"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old way of setting up the platform.

    Can only be called when a user accidentally mentions the platform in their
    config. But even in that case it would have been ignored.
    """


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Daikin climate based on config_entry."""
    daikin_api = hass.data[DAIKIN_DOMAIN][entry.entry_id]
    zones = daikin_api.device.zones
    if zones:
        async_add_entities(
            [
                DaikinZoneSwitch(daikin_api, zone_id)
                for zone_id, zone in enumerate(zones)
                if zone != ("-", "0")
            ]
        )


class DaikinZoneSwitch(ToggleEntity):
    """Representation of a zone."""

    def __init__(self, daikin_api, zone_id):
        """Initialize the zone."""
        self._api = daikin_api
        self._zone_id = zone_id

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._api.mac}-zone{self._zone_id}"

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ZONE_ICON

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._api.name} {self._api.device.zones[self._zone_id][0]}"

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._api.device.zones[self._zone_id][1] == "1"

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return self._api.device_info

    async def async_update(self):
        """Retrieve latest state."""
        await self._api.async_update()

    async def async_turn_on(self, **kwargs):
        """Turn the zone on."""
        await self._api.device.set_zone(self._zone_id, "1")

    async def async_turn_off(self, **kwargs):
        """Turn the zone off."""
        await self._api.device.set_zone(self._zone_id, "0")
