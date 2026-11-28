"""Cover platform for the ESI R2D7 integration."""

from collections.abc import Awaitable
from typing import Any, override

from esi_r2d7 import R2D7Connection

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_FIRST_CHANNEL,
    CONF_LAST_CHANNEL,
    CONF_SYSTEM,
    DOMAIN,
    LINK_ERRORS,
    R2D7ConfigEntry,
)

# The controller reports nothing back. A Stop is universal, so it marks as
# unknown the blind it was pressed on plus every blind sent Open or Close
# within this many seconds.
RECENT_MOVE_SECONDS = 120


def _stopped_signal(entry_id: str) -> str:
    """Return the signal that carries the channels a Stop applies to."""
    return f"{DOMAIN}_{entry_id}_stopped"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: R2D7ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the ESI R2D7 blinds."""
    async_add_entities(
        R2D7Blind(entry.runtime_data, entry, channel)
        for channel in range(
            entry.data[CONF_FIRST_CHANNEL], entry.data[CONF_LAST_CHANNEL] + 1
        )
    )


class R2D7Blind(CoverEntity):
    """A blind on one R2D7 channel.

    The R2D7 reports nothing back, so the state is the last command sent.
    """

    _attr_assumed_state = True
    _attr_device_class = CoverDeviceClass.BLIND
    _attr_has_entity_name = True
    _attr_is_closed: bool | None = None
    _attr_should_poll = False
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )
    _attr_translation_key = "blind"

    def __init__(
        self, connection: R2D7Connection, entry: R2D7ConfigEntry, channel: int
    ) -> None:
        """Initialize the blind."""
        self._connection = connection
        self._channel = channel
        self._stopped_signal = _stopped_signal(entry.entry_id)
        system = entry.data[CONF_SYSTEM]
        self._attr_translation_placeholders = {"channel": f"{channel:02d}"}
        self._attr_unique_id = f"{entry.entry_id}_{channel}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="ESI",
            model="R2D7",
            name=f"ESI R2D7 system {system}",
        )

    @property
    @override
    def available(self) -> bool:
        """Return if the serial link is up."""
        return super().available and self._connection.connected

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to link changes and system-wide stops."""
        self.async_on_remove(self._connection.add_listener(self.async_write_ha_state))
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._stopped_signal, self._handle_stopped
            )
        )

    @callback
    def _handle_stopped(self, channels: set[int]) -> None:
        """Mark the blind as position unknown when a Stop may have caught it."""
        if self._channel in channels:
            self._attr_is_closed = None
            self.async_write_ha_state()

    async def _send(self, command: Awaitable[None]) -> None:
        """Send a command, translating link errors."""
        try:
            await command
        except LINK_ERRORS:
            # No cause: its text can carry the port URL and its API key.
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            ) from None

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the blind."""
        await self._send(self._connection.open_blind(self._channel))
        self._attr_is_closed = False
        self.async_write_ha_state()

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the blind."""
        await self._send(self._connection.close_blind(self._channel))
        self._attr_is_closed = True
        self.async_write_ha_state()

    @override
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop every moving blind on this R2D7 system.

        The R2D7 has no per-blind stop: a Stop always reaches the whole system.
        """
        await self._send(self._connection.stop_system())
        channels = self._connection.take_recently_moved(RECENT_MOVE_SECONDS)
        async_dispatcher_send(
            self.hass, self._stopped_signal, channels | {self._channel}
        )
