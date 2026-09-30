"""Live event stream for the Peblar integration."""

import asyncio

from peblar import Peblar, PeblarError, PeblarSessionStatus

from homeassistant.core import HomeAssistant, callback

from .const import EVENT_STREAM_RETRY_MAXIMUM, EVENT_STREAM_RETRY_MINIMUM, LOGGER
from .coordinator import PeblarConfigEntry, PeblarDataUpdateCoordinator


class PeblarSessionListener:
    """Follows the charging session over the charger's event stream.

    The charger pushes a session change as it happens, which the poll
    would otherwise take up to its interval to notice. This only tells the
    poll to catch up early, so a stream that never comes up, or one that
    falls over, costs nothing beyond going back to the poll on its own.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: PeblarConfigEntry,
        peblar: Peblar,
        coordinator: PeblarDataUpdateCoordinator,
    ) -> None:
        """Initialize the listener."""
        self._hass = hass
        self._entry = entry
        self._peblar = peblar
        self._coordinator = coordinator
        self._retry = EVENT_STREAM_RETRY_MINIMUM

    async def async_run(self) -> None:
        """Keep a subscription up for as long as the entry is loaded."""
        self._retry = EVENT_STREAM_RETRY_MINIMUM

        while True:
            try:
                await self._async_listen()
            except PeblarError as error:
                LOGGER.debug(
                    "Peblar event stream for %s stopped: %s", self._entry.title, error
                )

            await asyncio.sleep(self._retry.total_seconds())
            self._retry = min(self._retry * 2, EVENT_STREAM_RETRY_MAXIMUM)

    async def _async_listen(self) -> None:
        """Open the stream and stay on it until it closes."""
        websocket = self._peblar.websocket()
        try:
            await websocket.connect()
            await websocket.subscribe_session_status(self._handle_session_status)

            # A charger that was unreachable at startup can leave the wait
            # at its longest. A subscription that landed settles that, so a
            # drop hours later is not held against whatever went before.
            # Taking the socket without ever getting this far is not a
            # working stream, and keeps backing off.
            self._retry = EVENT_STREAM_RETRY_MINIMUM

            await websocket.listen()
        finally:
            await websocket.disconnect()

    @callback
    def _handle_session_status(self, status: PeblarSessionStatus) -> None:
        """Ask the poll to catch up, now the session has moved on.

        The charger sends the current status right after subscribing, so
        the first call says nothing new. Refreshing anyway is harmless and
        cheaper than working out which one that was.
        """
        LOGGER.debug("Peblar session for %s is %s", self._entry.title, status.state)
        self._entry.async_create_task(
            self._hass, self._coordinator.async_request_refresh(), eager_start=False
        )
