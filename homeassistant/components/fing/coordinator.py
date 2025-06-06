"""DataUpdateCoordinator for Fing integration."""

from contextlib import suppress
from datetime import timedelta
import logging

from fing_agent_api import FingAgent
from fing_agent_api.models import AgentInfoResponse, Device
import httpx

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_IP_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class FingDataObject:
    """Fing Data Object."""

    def __init__(
        self,
        network_id: str | None = None,
        agent_info: AgentInfoResponse | None = None,
        devices: dict[str, Device] | None = None,
    ) -> None:
        """Initialize FingDataObject."""
        self.network_id = network_id
        self.agent_info = agent_info
        self.devices = devices if devices is not None else {}


class FingDataUpdateCoordinator(DataUpdateCoordinator[FingDataObject]):
    """Class to manage fetching data from Fing Agent."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize global Fing updater."""
        self._fing = FingAgent(
            config_entry.data[CONF_IP_ADDRESS],
            int(config_entry.data[CONF_PORT]),
            config_entry.data[CONF_API_KEY],
        )
        update_interval = timedelta(seconds=30)
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _async_update_data(self) -> FingDataObject:
        """Fetch data from Fing Agent."""
        device_response = None
        agent_info_response = None
        try:
            device_response = await self._fing.get_devices()

            with suppress(Exception):
                # The suppression is needed because the get_agent_info method isn't available for desktop agents
                agent_info_response = await self._fing.get_agent_info()

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
            httpx.CookieConflict,
            httpx.StreamError,
        ) as err:
            raise UpdateFailed("Unexpected error from HTTP request") from err

        if device_response is not None:
            return FingDataObject(
                device_response.network_id,
                agent_info_response,
                {device.mac: device for device in device_response.devices},
            )

        raise UpdateFailed("get_device failed. Response is None")
