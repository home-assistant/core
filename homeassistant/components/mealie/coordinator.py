"""Define an object to manage fetching Mealie data."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from aiomealie import (
    MealieAuthenticationError,
    MealieClient,
    MealieConnectionError,
    Mealplan,
    MealplanEntryType,
)

from homeassistant.const import CONF_API_TOKEN, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import LOGGER

if TYPE_CHECKING:
    from . import MealieConfigEntry

WEEK = timedelta(days=7)


class MealieCoordinator(DataUpdateCoordinator[dict[MealplanEntryType, list[Mealplan]]]):
    """Class to manage fetching Mealie data."""

    config_entry: MealieConfigEntry

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass, logger=LOGGER, name="Mealie", update_interval=timedelta(hours=1)
        )
        self.client = MealieClient(
            self.config_entry.data[CONF_HOST],
            token=self.config_entry.data[CONF_API_TOKEN],
            session=async_get_clientsession(hass),
        )

    async def _async_update_data(self) -> dict[MealplanEntryType, list[Mealplan]]:
        next_week = dt_util.now() + WEEK
        try:
            data = (
                await self.client.get_mealplans(dt_util.now().date(), next_week.date())
            ).items
        except MealieAuthenticationError as error:
            raise ConfigEntryError("Authentication failed") from error
        except MealieConnectionError as error:
            raise UpdateFailed(error) from error
        res: dict[MealplanEntryType, list[Mealplan]] = {
            MealplanEntryType.BREAKFAST: [],
            MealplanEntryType.LUNCH: [],
            MealplanEntryType.DINNER: [],
            MealplanEntryType.SIDE: [],
        }
        for meal in data:
            res[meal.entry_type].append(meal)
        return res
