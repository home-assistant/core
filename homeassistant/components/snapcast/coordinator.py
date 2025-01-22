"""Data update coordinator for Snapcast server."""

from __future__ import annotations

import logging

from snapcast.control.server import Snapserver

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class SnapcastUpdateCoordinator(DataUpdateCoordinator[None]):
    """Data update coordinator for pushed data from Snapcast server."""

    def __init__(self, hass: HomeAssistant, host: str, port: int) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{host}:{port}",
            update_interval=None,  # Disable update interval as server pushes
        )

        self._server = Snapserver(hass.loop, host, port, True)
        self.last_update_success = False

        self._server.set_on_update_callback(self._on_update)
        self._server.set_new_client_callback(self._on_update)
        self._server.set_on_connect_callback(self._on_connect)
        self._server.set_on_disconnect_callback(self._on_disconnect)

    def _on_update(self) -> None:
        """Snapserver on_update callback."""
        # Assume availability if an update is received.
        self.last_update_success = True
        self.async_update_listeners()

    def _on_connect(self) -> None:
        """Snapserver on_connect callback."""
        self.last_update_success = True
        self.async_update_listeners()

    def _on_disconnect(self, ex):
        """Snapsever on_disconnect callback."""
        self.async_set_update_error(ex)

    async def _async_setup(self) -> None:
        """Perform async setup for the coordinator."""
        # Start the server
        try:
            await self._server.start()
        except OSError as ex:
            raise UpdateFailed from ex

    async def _async_update_data(self) -> None:
        """Empty update method since data is pushed."""

    async def disconnect(self) -> None:
        """Disconnect from the server."""
        self._server.set_on_update_callback(None)
        self._server.set_on_connect_callback(None)
        self._server.set_on_disconnect_callback(None)
        self._server.set_new_client_callback(None)
        self._server.stop()

    @property
    def server(self) -> Snapserver:
        """Get the Snapserver object."""
        return self._server
