"""Define an object to manage fetching Mealie data."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from datetime import timedelta

from aiomealie import (
    MealieAuthenticationError,
    MealieClient,
    MealieConnectionError,
    Mealplan,
    MealplanEntryType,
    ShoppingItem,
    ShoppingList,
    Statistics,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, LOGGER

WEEK = timedelta(days=7)


@dataclass
class MealieData:
    """Mealie data type."""

    client: MealieClient
    mealplan_coordinator: MealieMealplanCoordinator
    shoppinglist_coordinator: MealieShoppingListCoordinator
    statistics_coordinator: MealieStatisticsCoordinator


type MealieConfigEntry = ConfigEntry[MealieData]


class MealieDataUpdateCoordinator[_DataT](DataUpdateCoordinator[_DataT]):
    """Base coordinator."""

    config_entry: MealieConfigEntry
    _name: str
    _update_interval: timedelta

    def __init__(
        self, hass: HomeAssistant, config_entry: MealieConfigEntry, client: MealieClient
    ) -> None:
        """Initialize the Mealie data coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"Mealie {self._name}",
            update_interval=self._update_interval,
        )
        self.client = client

    async def _async_update_data(self) -> _DataT:
        """Fetch data from Mealie."""
        try:
            return await self._async_update_internal()
        except MealieAuthenticationError as error:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from error
        except MealieConnectionError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key=f"update_failed_{self._name}",
            ) from error

    @abstractmethod
    async def _async_update_internal(self) -> _DataT:
        """Fetch data from Mealie."""


class MealieMealplanCoordinator(
    MealieDataUpdateCoordinator[dict[MealplanEntryType, list[Mealplan]]]
):
    """Class to manage fetching Mealie data."""

    _name = "mealplan"
    _update_interval = timedelta(hours=1)

    async def _async_update_internal(self) -> dict[MealplanEntryType, list[Mealplan]]:
        next_week = dt_util.now() + WEEK
        current_date = dt_util.now().date()
        next_week_date = next_week.date()
        response = await self.client.get_mealplans(current_date, next_week_date)
        res: dict[MealplanEntryType, list[Mealplan]] = {
            type_: [] for type_ in MealplanEntryType
        }
        for meal in response.items:
            res[meal.entry_type].append(meal)
        return res


@dataclass
class ShoppingListData:
    """Data class for shopping list data."""

    shopping_list: ShoppingList
    items: list[ShoppingItem]


class MealieShoppingListCoordinator(
    MealieDataUpdateCoordinator[dict[str, ShoppingListData]]
):
    """Class to manage fetching Mealie Shopping list data."""

    _name = "shopping_list"
    _update_interval = timedelta(minutes=5)

    async def _async_update_internal(
        self,
    ) -> dict[str, ShoppingListData]:
        shopping_list_items = {}
        shopping_lists = (await self.client.get_shopping_lists()).items
        for shopping_list in shopping_lists:
            shopping_list_id = shopping_list.list_id

            shopping_items = (
                await self.client.get_shopping_items(shopping_list_id)
            ).items

            shopping_list_items[shopping_list_id] = ShoppingListData(
                shopping_list=shopping_list, items=shopping_items
            )
        return shopping_list_items


class MealieStatisticsCoordinator(MealieDataUpdateCoordinator[Statistics]):
    """Class to manage fetching Mealie Statistics data."""

    _name = "statistics"
    _update_interval = timedelta(minutes=15)

    async def _async_update_internal(
        self,
    ) -> Statistics:
        return await self.client.get_statistics()
