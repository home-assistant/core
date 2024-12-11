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
from bring_api.types import BringItemsResponse, BringList, BringUserSettingsResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class BringData(BringItemsResponse):
    """Coordinator data class."""


class BringDataUpdateCoordinator(DataUpdateCoordinator[list[BringData]]):
    """A Bring Data Update Coordinator."""

    config_entry: ConfigEntry
    user_settings: BringUserSettingsResponse
    lists: list[BringList]

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
        """Fetch the latest data from bring."""
        items = []

        try:
            self.lists = (await self.bring.load_lists())["lists"]
        except BringRequestException as e:
            raise UpdateFailed("Unable to connect and retrieve data from bring") from e
        except (BringParseException, KeyError) as e:
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

        for lst in self.lists:
            try:
                response = await self.bring.get_list(lst["listUuid"])
                items.append(BringData(**response))
            except BringRequestException as e:
                raise UpdateFailed(
                    "Unable to connect and retrieve data from bring"
                ) from e
            except BringParseException as e:
                raise UpdateFailed("Unable to parse response from bring") from e

        return items

    async def _async_setup(self) -> None:
        """Set up coordinator."""
        try:
            self.user_settings = await self.bring.get_all_user_settings()
        except (BringAuthException, BringRequestException, BringParseException) as e:
            raise UpdateFailed(
                "Unable to connect and retrieve user settings from bring"
            ) from e
