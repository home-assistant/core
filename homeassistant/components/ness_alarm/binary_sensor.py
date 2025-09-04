"""Support for Ness D8X/D16X zone binary sensors."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import CONF_MAX_SUPPORTED_ZONES, CONF_ZONES, DOMAIN, SIGNAL_ZONE_CHANGED

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ness zone binary sensors from a config entry."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    config = data["config"]

    entities = []

    # Total zones to create
    max_zones: int = config[CONF_MAX_SUPPORTED_ZONES]

    # Map custom names if any are provided
    custom_zones = {zone["id"]: zone["name"] for zone in config.get(CONF_ZONES, [])}

    # Generate sensors
    for zone_id in range(1, max_zones + 1):
        name = custom_zones.get(zone_id, f"Zone {zone_id}")
        entities.append(
            NessZoneSensor(
                zone_id,
                name,
                config_entry.entry_id,
            )
        )

    async_add_entities(entities)


class NessZoneSensor(BinarySensorEntity):
    """Representation of a Ness zone sensor."""

    def __init__(
        self,
        zone_id: int,
        name: str,
        entry_id: str,
    ) -> None:
        """Initialize the zone sensor."""
        self._zone_id = zone_id
        self._name = name
        self._entry_id = entry_id
        self._state = False

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_ZONE_CHANGED,
                self._handle_zone_change,
            )
        )

    @callback
    def _handle_zone_change(self, zone_id: int, state: bool) -> None:
        """Handle zone state changes."""
        if zone_id != self._zone_id:
            return

        self._state = state
        self.async_write_ha_state()

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry_id}_zone_{self._zone_id}"

    @property
    def name(self) -> str:
        """Return the name."""
        return self._name

    @property
    def is_on(self) -> bool:
        """Return true if sensor is on."""
        return self._state

    @property
    def device_class(self) -> BinarySensorDeviceClass:
        """Return the device class."""
        return BinarySensorDeviceClass.MOTION
