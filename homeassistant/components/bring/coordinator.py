"""DataUpdateCoordinator for the Bring! integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from bring_api import (
    Bring,
    BringAuthException,
    BringParseException,
    BringRequestException,
)
from bring_api.types import BringItemsResponse, BringList

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
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
            # try to recover by refreshing access token, otherwise
            # initiate reauth flow
            try:
                await self.bring.retrieve_new_access_token()
            except (BringRequestException, BringParseException) as exc:
                raise UpdateFailed("Refreshing authentication token failed") from exc
            except BringAuthException as exc:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="setup_authentication_exception",
                    translation_placeholders={CONF_EMAIL: self.bring.mail},
                ) from exc
            raise UpdateFailed(
                "Authentication failed but re-authentication was successful, trying again later"
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
