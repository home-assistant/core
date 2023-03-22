"""Support for Envisalink zone bypass switches."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import (
    CONF_ZONENAME,
    DATA_EVL,
    SIGNAL_ZONE_BYPASS_UPDATE,
    ZONE_SCHEMA,
    EnvisalinkDevice,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Envisalink switch entities."""
    if not discovery_info:
        return
    configured_zones = discovery_info["zones"]

    entities = []
    for zone_num in configured_zones:
        entity_config_data = ZONE_SCHEMA(configured_zones[zone_num])
        zone_name = f"{entity_config_data[CONF_ZONENAME]}_bypass"
        _LOGGER.debug("Setting up zone_bypass switch: %s", zone_name)

        entity = EnvisalinkSwitch(
            hass,
            zone_num,
            zone_name,
            hass.data[DATA_EVL].alarm_state["zone"][zone_num],
            hass.data[DATA_EVL],
        )
        entities.append(entity)

    async_add_entities(entities)


class EnvisalinkSwitch(EnvisalinkDevice, SwitchEntity):
    """Representation of an Envisalink switch."""

    def __init__(self, hass, zone_number, zone_name, info, controller):
        """Initialize the switch."""
        self._zone_number = zone_number

        super().__init__(zone_name, info, controller)

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_ZONE_BYPASS_UPDATE, self.async_update_callback
            )
        )

    @property
    def is_on(self):
        """Return the boolean response if the zone is bypassed."""
        return self._info["bypassed"]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send the bypass keypress sequence to toggle the zone bypass."""
        self._controller.toggle_zone_bypass(self._zone_number)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the bypass keypress sequence to toggle the zone bypass."""
        self._controller.toggle_zone_bypass(self._zone_number)

    @callback
    def async_update_callback(self, bypass_map):
        """Update the zone bypass state in HA, if needed."""
        if bypass_map is None or self._zone_number in bypass_map:
            _LOGGER.debug("Bypass state changed for zone %d", self._zone_number)
            self.async_write_ha_state()
