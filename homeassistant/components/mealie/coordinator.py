"""Define an object to manage fetching Mealie data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

from aiomealie import MealieClient, MealieConnectionError, Mealplan, MealplanEntryType

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import LOGGER

if TYPE_CHECKING:
    from . import MealieConfigEntry


@dataclass
class MealieMealPlan:
    """Class to hold Mealie meal plan data."""

    breakfast: list[Mealplan]
    lunch: list[Mealplan]
    dinner: list[Mealplan]
    side: list[Mealplan]


class MealieCoordinator(DataUpdateCoordinator[MealieMealPlan]):
    """Class to manage fetching Mealie data."""

    config_entry: MealieConfigEntry

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass, logger=LOGGER, name="Mealie", update_interval=timedelta(hours=1)
        )
        self.client = MealieClient(
            self.config_entry.data[CONF_HOST], session=async_get_clientsession(hass)
        )

    async def _async_update_data(self) -> MealieMealPlan:
        next_week = dt_util.now() + timedelta(days=7)
        try:
            data = (
                await self.client.get_mealplans(dt_util.now().date(), next_week.date())
            ).items
        except MealieConnectionError as error:
            raise UpdateFailed(error) from error
        return MealieMealPlan(
            breakfast=[
                meal for meal in data if meal.entry_type is MealplanEntryType.BREAKFAST
            ],
            lunch=[meal for meal in data if meal.entry_type is MealplanEntryType.LUNCH],
            dinner=[
                meal for meal in data if meal.entry_type is MealplanEntryType.DINNER
            ],
            side=[meal for meal in data if meal.entry_type is MealplanEntryType.SIDE],
        )
