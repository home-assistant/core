"""DataUpdateCoordinator for Fing integration."""

from datetime import timedelta
import logging

from fing_agent_api import FingAgent
from fing_agent_api.models import Device
import httpx

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import AGENT_IP, AGENT_KEY, AGENT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class FingDataObject:
    """Fing Data Object."""

    def __init__(
        self, network_id: str | None = None, devices: dict[str, Device] | None = None
    ) -> None:
        """Initialize FingDataObject."""
        self.network_id = network_id
        self.devices = devices if devices is not None else {}


class FingDataUpdateCoordinator(DataUpdateCoordinator[FingDataObject]):
    """Class to manage fetching data from Fing Agent."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize global Fing updater."""
        self._hass = hass
        self._fing = FingAgent(
            config_entry.data[AGENT_IP],
            int(config_entry.data[AGENT_PORT]),
            config_entry.data[AGENT_KEY],
        )
        update_interval = timedelta(seconds=30)
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _async_update_data(self) -> FingDataObject:
        """Fetch data from Fing Agent."""
        try:
            response = await self._fing.get_devices()
            return FingDataObject(
                response.network_id, {device.mac: device for device in response.devices}
            )
        except httpx.NetworkError as err:
            raise UpdateFailed("Failed to connect") from err
        except httpx.TimeoutException as err:
            raise UpdateFailed("Timeout establishing connection") from err
        except httpx.HTTPStatusError as err:
            if err.response.status_code == 401:
                raise UpdateFailed("Invalid API key") from err
            raise UpdateFailed(
                f"Http request failed -> {err.response.status_code} - {err.response.reason_phrase}"
            ) from err
        except httpx.InvalidURL as err:
            raise UpdateFailed("Invalid hostname or IP address") from err
        except (
            httpx.HTTPError,
            httpx.InvalidURL,
            httpx.CookieConflict,
            httpx.StreamError,
        ) as err:
            raise UpdateFailed("Unexpected error from HTTP request") from err
