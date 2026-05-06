"""Common entity for Honeywell String Lights integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import Event, EventStateChangedData, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change_event

from .const import CONF_TRANSMITTER, DOMAIN

_LOGGER = logging.getLogger(__name__)


class HoneywellStringLightsEntity(Entity):
    """Honeywell String Lights base entity."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the entity."""
        self._transmitter = entry.data[CONF_TRANSMITTER]
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Honeywell",
            model="String Lights",
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to transmitter entity state changes."""
        await super().async_added_to_hass()

        transmitter_entity_id = er.async_validate_entity_id(
            er.async_get(self.hass), self._transmitter
        )

        @callback
        def _async_transmitter_state_changed(
            event: Event[EventStateChangedData],
        ) -> None:
            """Handle transmitter entity state changes."""
            new_state = event.data["new_state"]
            transmitter_available = (
                new_state is not None and new_state.state != STATE_UNAVAILABLE
            )
            if transmitter_available != self.available:
                _LOGGER.info(
                    "Transmitter %s used by %s is %s",
                    transmitter_entity_id,
                    self.entity_id,
                    "available" if transmitter_available else "unavailable",
                )

                self._attr_available = transmitter_available
                self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [transmitter_entity_id],
                _async_transmitter_state_changed,
            )
        )

        # Set initial availability based on current transmitter entity state
        transmitter_state = self.hass.states.get(transmitter_entity_id)
        self._attr_available = (
            transmitter_state is not None
            and transmitter_state.state != STATE_UNAVAILABLE
        )
