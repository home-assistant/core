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


class BringDataUpdateCoordinator(DataUpdateCoordinator[list[BringData]]):
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

    async def _async_update_data(self) -> list[BringData]:
        try:
            lists_response = await self.hass.async_add_executor_job(
                self.bring.loadLists
            )
            lists = lists_response["lists"]
        except BringRequestException as e:
            _LOGGER.warning("Unable to connect and retrieve data from bring")
            raise UpdateFailed from e
        except BringParseException as e:
            _LOGGER.warning("Unable to parse response from bring")
            raise UpdateFailed from e

        for lst in lists:
            try:
                items = await self.hass.async_add_executor_job(
                    self.bring.getItems, lst["listUuid"]
                )
            except BringRequestException as e:
                _LOGGER.warning("Unable to connect and retrieve data from bring")
                raise UpdateFailed from e
            except BringParseException as e:
                _LOGGER.warning("Unable to parse response from bring")
                raise UpdateFailed from e
            lst["items"] = items["purchase"]

        return lists
