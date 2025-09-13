"""Support for Ness D8X/D16X zone binary sensors."""

from __future__ import annotations

import logging
from typing import cast

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SIGNAL_ZONE_CHANGED
from .const import (
    CONF_ID,
    CONF_MAX_SUPPORTED_ZONES,
    CONF_NAME,
    CONF_TYPE,
    CONF_ZONES,
    DEFAULT_MAX_SUPPORTED_ZONES,
    DOMAIN,
)

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
    max_zones: int = config_entry.options.get(
        CONF_MAX_SUPPORTED_ZONES,
        config_entry.data.get(CONF_MAX_SUPPORTED_ZONES, DEFAULT_MAX_SUPPORTED_ZONES),
    )

    # Map custom names and types if any are provided
    custom_zones = {}
    for zone in config.get(CONF_ZONES, []):
        zone_id = zone.get(CONF_ID)
        if zone_id:
            custom_zones[zone_id] = {
                CONF_NAME: zone.get(CONF_NAME, f"Zone {zone_id}"),
                CONF_TYPE: zone.get(CONF_TYPE, BinarySensorDeviceClass.MOTION),
            }

    for zone_id in range(1, max_zones + 1):
        if zone_id in custom_zones:
            name = custom_zones[zone_id][CONF_NAME]
            zone_type = custom_zones[zone_id][CONF_TYPE]
        else:
            name = f"Zone {zone_id}"
            zone_type = BinarySensorDeviceClass.MOTION

        entities.append(
            NessZoneSensor(
                zone_id,
                name,
                zone_type,
                config_entry.entry_id,
            )
        )

    async_add_entities(entities)


class NessZoneSensor(BinarySensorEntity):
    """Representation of a Ness zone sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        zone_id: int,
        name: str,
        zone_type: str,
        entry_id: str,
    ) -> None:
        """Initialize the zone sensor."""
        self._zone_id = zone_id
        self._name = name
        self._type = zone_type
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
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Return the class of this sensor."""
        return cast(BinarySensorDeviceClass, self._type)
