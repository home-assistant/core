"""DataUpdateCoordinator for the Bring! integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from bring_api.bring import Bring
from bring_api.exceptions import (
    BringAuthException,
    BringParseException,
    BringRequestException,
)
from bring_api.types import BringItemsResponse, BringList

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class BringData(BringList, BringItemsResponse):
    """Coordinator data class."""


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
            lists_response = await self.bring.load_lists()
        except BringRequestException as e:
            raise UpdateFailed("Unable to connect and retrieve data from bring") from e
        except BringParseException as e:
            raise UpdateFailed("Unable to parse response from bring") from e
        except BringAuthException as e:
            raise UpdateFailed(
                "Unable to retrieve data from bring, authentication failed"
            ) from e

        list_dict: dict[str, BringData] = {}
        for lst in lists_response["lists"]:
            try:
                items = await self.bring.get_list(lst["listUuid"])
            except BringRequestException as e:
                raise UpdateFailed(
                    "Unable to connect and retrieve data from bring"
                ) from e
            except BringParseException as e:
                raise UpdateFailed("Unable to parse response from bring") from e
            else:
                list_dict[lst["listUuid"]] = BringData(**lst, **items)

        return list_dict
