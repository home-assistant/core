"""DataUpdateCoordinator for the Cookidoo integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from cookidoo_api import (
    Cookidoo,
    CookidooActionException,
    CookidooAuthBotDetectionException,
    CookidooAuthException,
    CookidooConfigException,
    CookidooItem,
    CookidooNavigationException,
    CookidooSelectorException,
    CookidooUnavailableException,
    CookidooUnexpectedStateException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, TODO_ADDITIONAL_ITEMS, TODO_ITEMS

_LOGGER = logging.getLogger(__name__)

type CookidooConfigEntry = ConfigEntry[CookidooDataUpdateCoordinator]


class CookidooDataUpdateCoordinator(
    DataUpdateCoordinator[dict[str, list[CookidooItem]]]
):
    """A Cookidoo Data Update Coordinator."""

    config_entry: CookidooConfigEntry

    def __init__(self, hass: HomeAssistant, cookidoo: Cookidoo) -> None:
        """Initialize the Cookidoo data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=300),
        )
        self.cookidoo = cookidoo

    async def _async_update_data(self) -> dict[str, list[CookidooItem]]:
        try:
            items = await self.cookidoo.get_items(pending=True, checked=True)
            additional_items = await self.cookidoo.get_additional_items(
                pending=True, checked=True
            )
        except CookidooConfigException as e:
            raise UpdateFailed(
                "Unable to connect and retrieve data from cookidoo"
            ) from e
        except (
            CookidooUnavailableException,
            CookidooNavigationException,
            CookidooSelectorException,
            CookidooActionException,
            CookidooUnexpectedStateException,
        ) as e:
            raise UpdateFailed("Unable to parse response from cookidoo") from e
        except CookidooAuthException as e:
            # try to recover by refreshing access token, otherwise
            # initiate reauth flow
            try:
                await self.cookidoo.login(force_session_refresh=True)
            except CookidooAuthBotDetectionException as exc:
                raise UpdateFailed("Refreshing authentication token failed") from exc
            except CookidooAuthException as exc:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="setup_authentication_exception",
                    translation_placeholders={CONF_EMAIL: self.cookidoo._cfg["email"]},  # noqa: SLF001
                ) from exc
            raise UpdateFailed(
                "Authentication failed but re-authentication was successful, trying again later"
            ) from e

        list_dict: dict[str, list[CookidooItem]] = {}
        list_dict[TODO_ITEMS] = items
        list_dict[TODO_ADDITIONAL_ITEMS] = additional_items
        return list_dict
