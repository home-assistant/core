"""The EGS integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from epicstore_api import EpicGamesStoreAPI

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN

SCAN_INTERVAL = timedelta(days=1)

_LOGGER = logging.getLogger(__name__)


class EGSUpdateCoordinator(DataUpdateCoordinator[dict[str, list[dict[str, Any]]]]):
    """Class to manage fetching data from the Epic Game Store."""

    def __init__(
        self, hass: HomeAssistant, api: EpicGamesStoreAPI, locale: str
    ) -> None:
        """Initialize."""
        self._api = api
        self.locale = locale

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, list[dict[str, Any]]]:
        """Update data via library."""
        try:
            data = await self.hass.async_add_executor_job(self._api.get_free_games)
        except Exception as error:
            raise UpdateFailed(error) from error

        _LOGGER.debug(data)

        discount_games = filter(
            lambda game:
            # Only accessible from the Store, without a voucher code (effectiveDate is also much in the future "2099-01-01T00:00:00.000Z")
            not game["isCodeRedemptionOnly"]
            # Seen some null promotions even with isCodeRedemptionOnly to false (why ?)
            and game.get("promotions")
            and (
                # Current discount(s)
                game["promotions"]["promotionalOffers"]
                or
                # Upcoming discount(s)
                game["promotions"]["upcomingPromotionalOffers"]
            ),
            data["data"]["Catalog"]["searchStore"]["elements"],
        )

        return_data: dict[str, list[dict[str, Any]]] = self.data or {}
        for game in discount_games:
            game_free = is_free_game(game)
            game_title = game["title"]
            game_description = game["description"].strip()
            game_released_at = dt_util.parse_datetime(game["effectiveDate"])
            game_price = game["price"]["totalPrice"]["fmtPrice"]["originalPrice"]
            game_publisher = game["seller"]["name"]
            game_url = f"https://store.epicgames.com/{self.locale}/p/{game['catalogNs']['mappings'][0]['pageSlug']}"
            game_img_portrait = None
            game_img_landscape = None

            for image in game["keyImages"]:
                if image["type"] == "OfferImageTall":
                    game_img_portrait = image["url"]
                if image["type"] == "OfferImageWide":
                    game_img_landscape = image["url"]

            game_promotions = game["promotions"]["promotionalOffers"]
            upcoming_promotions = game["promotions"]["upcomingPromotionalOffers"]

            promotion_data = {}
            if game_promotions and game["price"]["totalPrice"]["discountPrice"] == 0:
                promotion_data = game_promotions[0]["promotionalOffers"][0]
            elif not game_promotions and upcoming_promotions:
                promotion_data = upcoming_promotions[0]["promotionalOffers"][0]

            return_data["free" if game_free else "discount"] = return_data.get(
                "free" if game_free else "discount", []
            )

            return_data["free" if game_free else "discount"].append(
                {
                    "title": game_title,
                    "description": game_description,
                    "released_at": game_released_at,
                    "original_price": game_price.replace("\xa0", " "),
                    "publisher": game_publisher,
                    "url": game_url,
                    "img_portrait": game_img_portrait,
                    "img_landscape": game_img_landscape,
                    "discount_start_at": dt_util.parse_datetime(
                        promotion_data["startDate"]
                    ),
                    "discount_end_at": dt_util.parse_datetime(
                        promotion_data["endDate"]
                    ),
                }
            )

        _LOGGER.debug(return_data)
        return return_data


def is_free_game(game: dict[str, Any]) -> bool:
    """Return if the game is free or will be free."""
    _LOGGER.warning(game)
    return (
        # Current free game(s)
        game["promotions"]["promotionalOffers"]
        and game["promotions"]["promotionalOffers"][0]["promotionalOffers"][0][
            "discountSetting"
        ]["discountPercentage"]
        == 0
        and
        # Checking current price, maybe not necessary
        game["price"]["totalPrice"]["discountPrice"] == 0
    ) or (
        # Upcoming free game(s)
        game["promotions"]["upcomingPromotionalOffers"]
        and game["promotions"]["upcomingPromotionalOffers"][0]["promotionalOffers"][0][
            "discountSetting"
        ]["discountPercentage"]
        == 0
    )
