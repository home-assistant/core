"""Cover platform for Somfy RTS."""

import logging
from typing import Any

from rf_protocols.codes.somfy.rts import SomfyRTSButton
from rf_protocols.commands.somfy_rts import SomfyRTSCommand

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.components.radio_frequency import async_send_command
from homeassistant.const import STATE_CLOSED, STATE_OPEN, STATE_UNAVAILABLE
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_ADDRESS, CONF_TRANSMITTER, DOMAIN
from .entity import SomfyRTSConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SomfyRTSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Somfy RTS cover platform."""
    async_add_entities([SomfyRTSCover(config_entry)])


class SomfyRTSCover(CoverEntity, RestoreEntity):
    """A Somfy RTS cover controlled via RF."""

    _attr_assumed_state = True
    _attr_available = False
    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_has_entity_name = True
    _attr_is_closed: bool | None = None
    _attr_name = None
    _attr_should_poll = False
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    def __init__(self, entry: SomfyRTSConfigEntry) -> None:
        """Initialize the cover."""
        self._entry = entry
        self._transmitter: str = entry.data[CONF_TRANSMITTER]
        self._address: int = entry.data[CONF_ADDRESS]
        address_hex = format(self._address, "06X")
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Somfy",
            model="RTS Remote",
            name=f"Somfy RTS {address_hex}",
        )

    async def async_added_to_hass(self) -> None:
        """Restore last known state and subscribe to transmitter availability."""
        await super().async_added_to_hass()

        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state == STATE_OPEN:
                self._attr_is_closed = False
            elif last_state.state == STATE_CLOSED:
                self._attr_is_closed = True

        transmitter_entity_id = er.async_validate_entity_id(
            er.async_get(self.hass), self._transmitter
        )

        @callback
        def _async_transmitter_state_changed(
            event: Event[EventStateChangedData],
        ) -> None:
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
        """Transmit the command and persist the rolling code after success."""
        data = self._entry.runtime_data
        async with data.lock:
            rolling_code = data.rolling_code + 1
            command = SomfyRTSCommand(
                address=self._address,
                rolling_code=rolling_code,
                button=button,
                frame_repeats=frame_repeats,
            )
            await async_send_command(
                self.hass, self._transmitter, command, context=self._context
            )
            data.rolling_code = rolling_code
            await data.store.async_save({"rolling_code": data.rolling_code})

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._async_send_command(SomfyRTSButton.UP)
        self._attr_is_closed = False
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._async_send_command(SomfyRTSButton.DOWN)
        self._attr_is_closed = True
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self._async_send_command(SomfyRTSButton.MY)
