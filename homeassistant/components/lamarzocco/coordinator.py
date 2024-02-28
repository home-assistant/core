"""Coordinator for La Marzocco API."""
from collections.abc import Callable, Coroutine
from datetime import timedelta
import logging
from typing import Any

from lmcloud import LMCloud as LaMarzoccoClient
from lmcloud.exceptions import AuthFail, RequestNotSuccessful

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_MACHINE, DOMAIN

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


class LaMarzoccoUpdateCoordinator(DataUpdateCoordinator[None]):
    """Class to handle fetching data from the La Marzocco API centrally."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize coordinator."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.lm = LaMarzoccoClient(
            callback_websocket_notify=self.async_update_listeners,
        )
        self.local_connection_configured = (
            self.config_entry.data.get(CONF_HOST) is not None
        )

    async def _async_update_data(self) -> None:
        """Fetch data from API endpoint."""

        if not self.lm.initialized:
            await self._async_init_client()

        await self._async_handle_request(
            self.lm.update_local_machine_status, force_update=True
        )

        _LOGGER.debug("Current status: %s", str(self.lm.current_status))

    async def _async_init_client(self) -> None:
        """Initialize the La Marzocco Client."""

        # Initialize cloud API
        _LOGGER.debug("Initializing Cloud API")
        await self._async_handle_request(
            self.lm.init_cloud_api,
            credentials=self.config_entry.data,
            machine_serial=self.config_entry.data[CONF_MACHINE],
        )
        _LOGGER.debug("Model name: %s", self.lm.model_name)

        # initialize local API
        if (host := self.config_entry.data.get(CONF_HOST)) is not None:
            _LOGGER.debug("Initializing local API")
            await self.lm.init_local_api(
                host=host,
                client=get_async_client(self.hass),
            )

            _LOGGER.debug("Init WebSocket in Background Task")

            self.config_entry.async_create_background_task(
                hass=self.hass,
                target=self.lm.lm_local_api.websocket_connect(
                    callback=self.lm.on_websocket_message_received,
                    use_sigterm_handler=False,
                ),
                name="lm_websocket_task",
            )

        self.lm.initialized = True

    async def _async_handle_request(
        self,
        func: Callable[..., Coroutine[None, None, None]],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Handle a request to the API."""
        try:
            await func(*args, **kwargs)
        except AuthFail as ex:
            msg = "Authentication failed."
            _LOGGER.debug(msg, exc_info=True)
            raise ConfigEntryAuthFailed(msg) from ex
        except RequestNotSuccessful as ex:
            _LOGGER.debug(ex, exc_info=True)
            raise UpdateFailed("Querying API failed. Error: %s" % ex) from ex
