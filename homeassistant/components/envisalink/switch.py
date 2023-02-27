"""Support for Envisalink zone bypass switches."""
from __future__ import annotations

from pyenvisalink.const import STATE_CHANGE_ZONE_BYPASS

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_CREATE_ZONE_BYPASS_SWITCHES,
    CONF_ZONE_SET,
    CONF_ZONENAME,
    CONF_ZONES,
    DOMAIN,
    LOGGER,
)
from .helpers import find_yaml_info, parse_range_string
from .models import EnvisalinkDevice


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the zone bypass switches based on a config entry."""
    controller = hass.data[DOMAIN][entry.entry_id]

    create_bypass_switches = entry.options.get(CONF_CREATE_ZONE_BYPASS_SWITCHES)
    if create_bypass_switches:
        zone_spec: str = entry.data.get(CONF_ZONE_SET, "")
        zone_set = parse_range_string(
            zone_spec, min_val=1, max_val=controller.controller.max_zones
        )
        zone_info = entry.data.get(CONF_ZONES)
        if zone_set is not None:
            entities = []
            for zone_num in zone_set:
                zone_entry = find_yaml_info(zone_num, zone_info)

                entity = EnvisalinkSwitch(
                    hass,
                    zone_num,
                    zone_entry,
                    controller,
                )
                entities.append(entity)

            async_add_entities(entities)


class EnvisalinkSwitch(EnvisalinkDevice, SwitchEntity):
    """Representation of an Envisalink switch."""

    def __init__(self, hass, zone_number, zone_info, controller):
        """Initialize the switch."""
        self._zone_number = zone_number
        name = f"Zone {self._zone_number} Bypass"
        self._attr_unique_id = f"{controller.unique_id}_{name}"

        self._attr_has_entity_name = True
        if zone_info:
            # Override the name if there is info from the YAML configuration
            if CONF_ZONENAME in zone_info:
                name = f"{zone_info[CONF_ZONENAME]}_bypass"
                self._attr_has_entity_name = False

        LOGGER.debug("Setting up zone: %s", name)
        super().__init__(name, controller, STATE_CHANGE_ZONE_BYPASS, zone_number)

    @property
    def _info(self):
        return self._controller.controller.alarm_state["zone"][self._zone_number]

    @property
    def is_on(self):
        """Return the boolean response if the zone is bypassed."""
        return self._info["bypassed"]

    async def async_turn_on(self, **kwargs):
        """Send the bypass keypress sequence to toggle the zone bypass."""
        await self._controller.controller.toggle_zone_bypass(self._zone_number)

    async def async_turn_off(self, **kwargs):
        """Send the bypass keypress sequence to toggle the zone bypass."""
        await self._controller.controller.toggle_zone_bypass(self._zone_number)
