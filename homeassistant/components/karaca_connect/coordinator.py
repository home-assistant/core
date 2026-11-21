"""Update coordinator for Karaca Connect."""

from datetime import timedelta
import logging
from typing import Any, override

from karaca_connect_client import KaracaAuthError, KaracaClient, KaracaError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import UPDATE_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)


class KaracaCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch status from one Karaca device."""

    def __init__(
        self, hass: HomeAssistant, client: KaracaClient, entry: ConfigEntry[Any]
    ) -> None:
        """Initialize the Karaca cloud coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="Karaca Connect",
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.client = client

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest cloud details for the selected device."""
        try:
            return await self.client.get_detail()
        except KaracaAuthError as exc:
            raise ConfigEntryAuthFailed(
                "Karaca Connect authentication has expired"
            ) from exc
        except KaracaError as exc:
            raise UpdateFailed("Karaca cloud device state unavailable") from exc
