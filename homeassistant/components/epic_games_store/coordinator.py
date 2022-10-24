"""The EGS integration."""
from __future__ import annotations

from datetime import timedelta, datetime
import logging
from typing import Any

from epicstore_api import EpicGamesStoreAPI
import async_timeout

from homeassistant.core import HomeAssistant
from homeassistant.util import dt
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

# SCAN_INTERVAL = timedelta(days=1)
SCAN_INTERVAL = timedelta(minutes=2)

_LOGGER = logging.getLogger(__name__)


class EGSUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from the Epic Game Store."""

    def __init__(self, hass: HomeAssistant, api: EpicGamesStoreAPI) -> None:
        """Initialize."""
        self._api = api

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            data = await self.hass.async_add_executor_job(
                self._api.get_free_games
            )
        except Exception as error:
            raise UpdateFailed(error) from error

        promo_games = list(sorted(filter(lambda x: x.get('promotions'), data["data"]["Catalog"]["searchStore"][
            "elements"
        ]), key=lambda g: g['title']))


        return_data = self.data or {}
        for game in promo_games:
            prefix = ''
            # _LOGGER.error("-"*50)
            # _LOGGER.info(game)
            game_title = game['title']
            game_thumbnail = None
            game_url = game["catalogNs"]["mappings"][0]['pageSlug']
            game_url = f"https://store.epicgames.com/fr/p/{game_url}"
            game_promotion_data = {}

            for image in game['keyImages']:
                if image['type'] == 'Thumbnail':
                    game_thumbnail = image['url']

            # _LOGGER.warning(game_thumbnail)
            # _LOGGER.warning(game_url)
            # _LOGGER.error("-"*50)
            game_price = game['price']['totalPrice']['fmtPrice']['originalPrice']
            try:
                game_promotions = game['promotions']['promotionalOffers']
                upcoming_promotions = game['promotions']['upcomingPromotionalOffers']
                if not game_promotions and upcoming_promotions:
                    # Promotion is not active yet, but will be active soon.
                    game_promotion_data = upcoming_promotions[0]['promotionalOffers'][0]
                    print('{} ({}) will be free from {} to {} UTC.'.format(
                        game_title, game_price, game_promotion_data['startDate'], game_promotion_data['endDate']
                    ))

                    prefix = "next_"
                elif len(game_promotions) > 0:
                    print('{} ({}) is FREE now.'.format(
                        game_title, game_price
                    ))
                    _LOGGER.error(game_promotions)
                    _LOGGER.warning("-"*100)

                    game_promotion_data = game_promotions[0]['promotionalOffers'][0]
            except TypeError:
                pass
                # or
                #print('No discounts for this game')
                # your choice

            if game_promotion_data:
                suffix="1"
                if return_data.get(f"{prefix}free_game_{suffix}"):
                    suffix = "2"
                
                return_data[f"{prefix}free_game_{suffix}"]={
                    'title': game_title,
                    'url': game_url,
                    'thumbnail': game_thumbnail,
                    'original_price': game_price,
                    'start_at': dt.parse_datetime(game_promotion_data['startDate']),
                    'end_at': dt.parse_datetime(game_promotion_data['endDate']),
                }
        _LOGGER.warning("-"*200)


        return return_data
