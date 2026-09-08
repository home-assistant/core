"""Support for Envisalink zone bypass switches.

Not currently loaded as a platform (Platform.SWITCH is not in PLATFORMS) due to
an issue with some panels; kept for a future re-enablement after further
refactoring of the integration.
"""

import logging
from typing import Any, override

from pyenvisalink import EnvisalinkAlarmPanel

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EnvisalinkConfigEntry
from .const import (
    CONF_ZONE_NUMBER,
    CONF_ZONENAME,
    SIGNAL_ZONE_BYPASS_UPDATE,
    SUBENTRY_TYPE_ZONE,
)
from .entity import EnvisalinkEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EnvisalinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Envisalink zone bypass switch entities from a config entry."""
    controller = entry.runtime_data

    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_ZONE):
        zone_number = subentry.data[CONF_ZONE_NUMBER]
        zone_name = subentry.data[CONF_ZONENAME]
        _LOGGER.debug("Setting up zone_bypass switch for zone: %s", zone_name)

        entity = EnvisalinkSwitch(
            zone_number,
            zone_name,
            controller.alarm_state["zone"][zone_number],
            controller,
        )
        async_add_entities([entity], config_subentry_id=subentry.subentry_id)


class EnvisalinkSwitch(EnvisalinkEntity, SwitchEntity):
    """Representation of an Envisalink switch."""

    def __init__(
        self,
        zone_number: int,
        zone_name: str,
        info: dict[str, Any],
        controller: EnvisalinkAlarmPanel,
    ) -> None:
        """Initialize the switch."""
        self._zone_number = zone_number

        super().__init__(f"{zone_name} Bypass", info, controller)

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_ZONE_BYPASS_UPDATE, self.async_update_callback
            )
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return the boolean response if the zone is bypassed."""
        return self._info["bypassed"]

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send the bypass keypress sequence to toggle the zone bypass."""
        self._controller.toggle_zone_bypass(self._zone_number)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the bypass keypress sequence to toggle the zone bypass."""
        self._controller.toggle_zone_bypass(self._zone_number)

    @callback
    def async_update_callback(self, bypass_map):
        """Update the zone bypass state in HA, if needed."""
        if bypass_map is None or self._zone_number in bypass_map:
            _LOGGER.debug("Bypass state changed for zone %d", self._zone_number)
            self.async_write_ha_state()
