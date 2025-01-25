"""DataUpdateCoordinator for the Cookidoo integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from cookidoo_api import (
    Cookidoo,
    CookidooAdditionalItem,
    CookidooAuthException,
    CookidooException,
    CookidooIngredientItem,
    CookidooRequestException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type CookidooConfigEntry = ConfigEntry[CookidooDataUpdateCoordinator]


@dataclass
class CookidooData:
    """Cookidoo data type."""

    ingredient_items: list[CookidooIngredientItem]
    additional_items: list[CookidooAdditionalItem]


class CookidooDataUpdateCoordinator(DataUpdateCoordinator[CookidooData]):
    """A Cookidoo Data Update Coordinator."""

    config_entry: CookidooConfigEntry

    def __init__(
        self, hass: HomeAssistant, cookidoo: Cookidoo, entry: CookidooConfigEntry
    ) -> None:
        """Initialize the Cookidoo data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=90),
            config_entry=entry,
        )
        self.cookidoo = cookidoo

    async def _async_setup(self) -> None:
        try:
            await self.cookidoo.login()
        except CookidooRequestException as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="setup_request_exception",
            ) from e
        except CookidooAuthException as e:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="setup_authentication_exception",
                translation_placeholders={
                    CONF_EMAIL: self.config_entry.data[CONF_EMAIL]
                },
            ) from e

    async def _async_update_data(self) -> CookidooData:
        try:
            ingredient_items = await self.cookidoo.get_ingredient_items()
            additional_items = await self.cookidoo.get_additional_items()
        except CookidooAuthException:
            try:
                await self.cookidoo.refresh_token()
            except CookidooAuthException as exc:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="setup_authentication_exception",
                    translation_placeholders={
                        CONF_EMAIL: self.config_entry.data[CONF_EMAIL]
                    },
                ) from exc
            _LOGGER.debug(
                "Authentication failed but re-authentication was successful, trying again later"
            )
            return self.data
        except CookidooException as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_exception",
            ) from e

        return CookidooData(
            ingredient_items=ingredient_items, additional_items=additional_items
        )
