"""DataUpdateCoordinator for Fing integration."""

from contextlib import suppress
from dataclasses import dataclass, field
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

type FingConfigEntry = ConfigEntry[FingDataUpdateCoordinator]


@dataclass
class FingDataObject:
    """Fing Data Object."""

    network_id: str | None = None
    agent_info: AgentInfoResponse | None = None
    devices: dict[str, Device] = field(default_factory=dict)


class FingDataUpdateCoordinator(DataUpdateCoordinator[FingDataObject]):
    """Class to manage fetching data from Fing Agent."""

    def __init__(self, hass: HomeAssistant, config_entry: FingConfigEntry) -> None:
        """Initialize global Fing updater."""
        self._fing = FingAgent(
            ip=config_entry.data[CONF_IP_ADDRESS],
            port=int(config_entry.data[CONF_PORT]),
            key=config_entry.data[CONF_API_KEY],
        )
        update_interval = timedelta(seconds=30)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
            config_entry=config_entry,
        )

    async def _async_update_data(self) -> FingDataObject:
        """Fetch data from Fing Agent."""
        device_response = None
        agent_info_response = None
        try:
            device_response = await self._fing.get_devices()

            with suppress(httpx.ConnectError):
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
        else:
            agent_id = device_response.network_id
            if agent_info_response is not None:
                agent_id = agent_info_response.agent_id

            return FingDataObject(
                device_response.network_id,
                agent_info_response,
                {
                    self.create_unique_id(agent_id, device.mac): device
                    for device in device_response.devices
                },
            )

    def create_unique_id(self, agent_id: str, mac_address: str) -> str:
        """Create a unique ID for a device."""
        return f"{agent_id}-{mac_address}"
