"""Define an object to manage fetching Mealie data."""

from __future__ import annotations

from datetime import timedelta

from aiomealie import (
    MealieAuthenticationError,
    MealieClient,
    MealieConnectionError,
    Mealplan,
    MealplanEntryType,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import LOGGER

WEEK = timedelta(days=7)

type MealieConfigEntry = ConfigEntry[MealieCoordinator]


class MealieCoordinator(DataUpdateCoordinator[dict[MealplanEntryType, list[Mealplan]]]):
    """Class to manage fetching Mealie data."""

    config_entry: MealieConfigEntry

    def __init__(self, hass: HomeAssistant, client: MealieClient) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass, logger=LOGGER, name="Mealie", update_interval=timedelta(hours=1)
        )
        self.client = client

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
