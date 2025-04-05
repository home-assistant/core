"""Coordinators for the UniFi Access integration."""

from asyncio import CancelledError, Task
from contextlib import suppress
import logging

from uiaccessclient import ApiClient, Door, NotificationEvent, SpaceApi, WebsocketClient
from uiaccessclient.openapi.exceptions import (
    ApiException,
    ForbiddenException,
    UnauthorizedException,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class UniFiAccessDoorCoordinator(DataUpdateCoordinator[dict[str, Door]]):
    """Handles refreshing door data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: ApiClient,
        websocket_client: WebsocketClient,
    ) -> None:
        """Initialize the door coordinator class."""
        super().__init__(
            hass,
            _LOGGER,
            name="UniFi Access door",
            always_update=False,
        )

        self.task: Task[None] | None = None
        self.space_api = SpaceApi(api_client)
        self.websocket_client = websocket_client

    async def _async_setup(self) -> None:
        self.task = self.hass.async_create_task(
            self.receive_updated_data(), eager_start=True
        )

    async def async_shutdown(self) -> None:
        """Cancel any scheduled call, and ignore new runs."""
        await super().async_shutdown()

        if self.task is not None:
            self.task.cancel()
            with suppress(CancelledError):
                await self.task

    async def _async_update_data(self) -> dict[str, Door]:
        return await self.hass.async_add_executor_job(self._update_data)

    async def receive_updated_data(self) -> None:
        """Start websocket receiver for updated data from UniFi Access."""
        _LOGGER.debug("Starting UniFi Access websocket")
        try:
            async with self.websocket_client.device_notifications() as socket:
                async for message in socket:
                    _LOGGER.debug(
                        "Received update from UniFi Access: %s", message.event
                    )

                    if message.event == NotificationEvent.DeviceUpdateV2:
                        # WebSocket API is poorly documented so we will just use the REST API whenever we get
                        # an update to fetch all the relevant data.
                        self.async_set_updated_data(
                            await self.hass.async_add_executor_job(self._update_data)
                        )
        except Exception as exc:
            _LOGGER.error("Error in UniFi Access websocket receiver: %s", exc)
            raise

        _LOGGER.debug("UniFi Access websocket receiver has been cancelled")

    def _update_data(self) -> dict[str, Door]:
        _LOGGER.debug("Refreshing UniFi Access door data")
        try:
            response = self.space_api.fetch_all_doors()
        except (
            UnauthorizedException,
            ForbiddenException,
        ) as err:
            raise ConfigEntryAuthFailed from err
        except ApiException as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        return {door.id: door for door in response.data if door.is_bind_hub}
