"""Update coordinator for Karaca Connect."""

from datetime import timedelta
import logging
from typing import Any

from karaca_connect_client import KaracaAuthError, KaracaClient, KaracaError

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import UPDATE_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)


class KaracaCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch status from one Karaca device."""

    def __init__(self, hass, client: KaracaClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="Karaca Connect",
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.client.get_detail()
        except KaracaAuthError as exc:
            raise ConfigEntryAuthFailed("Karaca Connect authentication has expired") from exc
        except KaracaError as exc:
            raise UpdateFailed("Karaca cloud device state unavailable") from exc
