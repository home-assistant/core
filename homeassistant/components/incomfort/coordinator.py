"""Datacoordinator for InComfort integration."""

from dataclasses import dataclass, field
from datetime import timedelta
import logging
from typing import Any

from aiohttp import ClientResponseError
from incomfortclient import (
    Gateway as InComfortGateway,
    Heater as InComfortHeater,
    IncomfortError,
)

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = 30


@dataclass
class InComfortData:
    """Keep the Intergas InComfort entry data."""

    client: InComfortGateway
    heaters: list[InComfortHeater] = field(default_factory=list)


async def async_connect_gateway(
    hass: HomeAssistant,
    entry_data: dict[str, Any],
) -> InComfortData:
    """Validate the configuration."""
    credentials = dict(entry_data)
    hostname = credentials.pop(CONF_HOST)

    client = InComfortGateway(
        hostname, **credentials, session=async_get_clientsession(hass)
    )
    heaters = await client.heaters()

    return InComfortData(client=client, heaters=heaters)


class InComfortDataCoordinator(DataUpdateCoordinator[InComfortData]):
    """Data coordinator for InComfort entities."""

    def __init__(self, hass: HomeAssistant, incomfort_data: InComfortData) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="InComfort datacoordinator",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.incomfort_data = incomfort_data

    async def _async_update_data(self) -> InComfortData:
        """Fetch data from API endpoint."""
        try:
            for heater in self.incomfort_data.heaters:
                await heater.update()
        except TimeoutError as exc:
            raise UpdateFailed from exc
        except IncomfortError as exc:
            if isinstance(exc.message, ClientResponseError):
                if exc.message.status == 401:
                    raise ConfigEntryError("Incorrect credentials") from exc
            raise UpdateFailed from exc
        return self.incomfort_data
