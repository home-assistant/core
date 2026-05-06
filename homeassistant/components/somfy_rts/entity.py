"""Common entity for the Somfy RTS integration."""

import logging

from rf_protocols import SomfyRTSButton, SomfyRTSCommand

from homeassistant.components.radio_frequency import async_send_command
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import Event, EventStateChangedData, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store

from .const import CONF_ADDRESS, CONF_TRANSMITTER, DOMAIN

_LOGGER = logging.getLogger(__name__)


class SomfyRTSData:
    """Shared runtime data for a Somfy RTS config entry."""

    def __init__(self, *, store: Store, rolling_code: int) -> None:
        """Initialize runtime data."""
        self.store = store
        self.rolling_code = rolling_code


type SomfyRTSConfigEntry = ConfigEntry[SomfyRTSData]


class SomfyRTSEntity(Entity):
    """Somfy RTS base entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: SomfyRTSConfigEntry) -> None:
        """Initialize the entity."""
        self._entry = entry
        self._transmitter: str = entry.data[CONF_TRANSMITTER]
        self._address: int = entry.data[CONF_ADDRESS]
        address_hex = format(self._address, "06X")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Somfy",
            model="RTS Remote",
            name=f"Somfy RTS {address_hex}",
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

        transmitter_state = self.hass.states.get(transmitter_entity_id)
        self._attr_available = (
            transmitter_state is not None
            and transmitter_state.state != STATE_UNAVAILABLE
        )

    async def _async_send_command(
        self, button: SomfyRTSButton, *, frame_repeats: int = 3
    ) -> None:
        """Increment the rolling code, persist it, and transmit the command."""
        data = self._entry.runtime_data
        data.rolling_code += 1
        await data.store.async_save({"rolling_code": data.rolling_code})
        command = SomfyRTSCommand(
            address=self._address,
            rolling_code=data.rolling_code,
            button=button,
            frame_repeats=frame_repeats,
        )
        await async_send_command(
            self.hass, self._transmitter, command, context=self._context
        )
