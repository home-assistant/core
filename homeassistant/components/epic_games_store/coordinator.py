"""The Epic Games Store integration data coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from epicstore_api import EpicGamesStoreAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_COUNTRY, CONF_LANGUAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, CalendarType
from .helper import format_game_data

SCAN_INTERVAL = timedelta(days=1)

_LOGGER = logging.getLogger(__name__)


class EGSCalendarUpdateCoordinator(
    DataUpdateCoordinator[dict[str, list[dict[str, Any]]]]
):
    """Class to manage fetching data from the Epic Game Store."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self._api = EpicGamesStoreAPI(
            entry.data[CONF_LANGUAGE],
            entry.data[CONF_COUNTRY],
        )
        self.language = entry.data[CONF_LANGUAGE]

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, list[dict[str, Any]]]:
        """Update data via library."""
        raw_data = await self.hass.async_add_executor_job(self._api.get_free_games)
        _LOGGER.debug(raw_data)
        data = raw_data["data"]["Catalog"]["searchStore"]["elements"]

        discount_games = filter(
            lambda game: game.get("promotions")
            and (
                # Current discount(s)
                game["promotions"]["promotionalOffers"]
                or
                # Upcoming discount(s)
                game["promotions"]["upcomingPromotionalOffers"]
            ),
            data,
        )

        return_data: dict[str, list[dict[str, Any]]] = {
            CalendarType.DISCOUNT: [],
            CalendarType.FREE: [],
        }
        for discount_game in discount_games:
            game = format_game_data(discount_game, self.language)

            if game["discount_type"]:
                return_data[game["discount_type"]].append(game)

        return_data[CalendarType.DISCOUNT] = sorted(
            return_data[CalendarType.DISCOUNT],
            key=lambda game: game["discount_start_at"],
        )
        return_data[CalendarType.FREE] = sorted(
            return_data[CalendarType.FREE], key=lambda game: game["discount_start_at"]
        )

        _LOGGER.debug(return_data)
        return return_data
