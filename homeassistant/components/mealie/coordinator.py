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
import homeassistant.util.dt as dt_util

from .const import LOGGER

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

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        client: MealieClient,
        update_interval: timedelta,
    ) -> None:
        """Initialize the Withings data coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=name,
            update_interval=update_interval,
        )
        self.client = client

    async def _async_update_data(self) -> _DataT:
        """Fetch data from Mealie."""
        try:
            return await self._async_update_internal()
        except MealieAuthenticationError as error:
            raise ConfigEntryAuthFailed from error
        except MealieConnectionError as error:
            raise UpdateFailed(error) from error

    @abstractmethod
    async def _async_update_internal(self) -> _DataT:
        """Fetch data from Mealie."""


class MealieMealplanCoordinator(
    MealieDataUpdateCoordinator[dict[MealplanEntryType, list[Mealplan]]]
):
    """Class to manage fetching Mealie data."""

    def __init__(self, hass: HomeAssistant, client: MealieClient) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            name="MealieMealplan",
            client=client,
            update_interval=timedelta(hours=1),
        )
        self.client = client

    async def _async_update_internal(self) -> dict[MealplanEntryType, list[Mealplan]]:
        next_week = dt_util.now() + WEEK
        data = (
            await self.client.get_mealplans(dt_util.now().date(), next_week.date())
        ).items
        res: dict[MealplanEntryType, list[Mealplan]] = {
            MealplanEntryType.BREAKFAST: [],
            MealplanEntryType.LUNCH: [],
            MealplanEntryType.DINNER: [],
            MealplanEntryType.SIDE: [],
        }
        for meal in data:
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

    def __init__(self, hass: HomeAssistant, client: MealieClient) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            name="MealieShoppingLists",
            client=client,
            update_interval=timedelta(minutes=5),
        )

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

    def __init__(self, hass: HomeAssistant, client: MealieClient) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            name="MealieStatistics",
            client=client,
            update_interval=timedelta(minutes=15),
        )

    async def _async_update_internal(
        self,
    ) -> Statistics:
        return await self.client.get_statistics()
