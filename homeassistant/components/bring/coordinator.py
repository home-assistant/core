"""DataUpdateCoordinator for the Bring! integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from python_bring_api.bring import Bring
from python_bring_api.exceptions import BringParseException, BringRequestException
from python_bring_api.types import BringItemsResponse, BringList

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class BringData(BringList):
    """Coordinator data class."""

    items: list[BringItemsResponse]


class BringDataUpdateCoordinator(DataUpdateCoordinator[dict[str, BringData]]):
    """A Bring Data Update Coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, bring: Bring) -> None:
        """Initialize the Bring data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=90),
        )
        self.bring = bring

    async def _async_update_data(self) -> dict[str, BringData]:
        try:
            lists_response = await self.bring.loadListsAsync()
        except BringRequestException as e:
            raise UpdateFailed("Unable to connect and retrieve data from bring") from e
        except BringParseException as e:
            raise UpdateFailed("Unable to parse response from bring") from e

        list_dict = {}
        for lst in lists_response["lists"]:
            try:
                items = await self.bring.getItemsAsync(lst["listUuid"])
            except BringRequestException as e:
                raise UpdateFailed(
                    "Unable to connect and retrieve data from bring"
                ) from e
            except BringParseException as e:
                raise UpdateFailed("Unable to parse response from bring") from e
            lst["items"] = items["purchase"]
            list_dict[lst["listUuid"]] = lst

        return list_dict
