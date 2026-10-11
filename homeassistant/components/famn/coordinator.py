"""DataUpdateCoordinators for the Famn integration."""

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, override

from famn_sdk import (
    ApiError,
    ListApi,
    ListItem,
    ListItemApi,
    ListModel,
    TaskItem,
    TaskList,
    TasksApi,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AUTH_FAILED_STATUS, FamnAuth
from .const import DOMAIN, LOGGER, TASK_TYPE_CHORES, TASK_TYPE_TODOS

# The realtime gateway pushes changes as they happen; polling stays on as
# a fallback for events missed while the WebSocket was down.
SCAN_INTERVAL = timedelta(minutes=15)

PAGE_SIZE = 100

# The Famn list types that behave like shopping lists; the same service also
# stores freezer/pantry inventories, which make no sense as todo entities.
SHOPPING_LIST_TYPES = ["grocery", "shopping"]

type FamnConfigEntry = ConfigEntry[FamnRuntimeData]


@dataclass(frozen=True)
class FamnChoreList:
    """A Famn chore list together with its open items."""

    task_list: TaskList
    items: list[TaskItem]


@dataclass(frozen=True)
class FamnShoppingList:
    """A Famn shopping list together with its open items."""

    shopping_list: ListModel
    items: list[ListItem]


class FamnChoresCoordinator(DataUpdateCoordinator[dict[str, FamnChoreList]]):
    """Coordinator fetching the chore lists of the paired space."""

    config_entry: FamnConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: FamnConfigEntry, auth: FamnAuth
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.auth = auth
        self.tasks_api = TasksApi(auth.client)

    @override
    async def _async_update_data(self) -> dict[str, FamnChoreList]:
        """Fetch the chore lists and their open items."""
        if TYPE_CHECKING:
            assert self.config_entry.unique_id is not None

        try:
            await self.auth.async_ensure_token_valid()
            task_lists = await self._async_fetch_task_lists(self.config_entry.unique_id)
            return {
                task_list.id: FamnChoreList(
                    task_list=task_list,
                    items=await self.tasks_api.get_task_items_endpoint(
                        task_list.id, completed=False
                    ),
                )
                for task_list in task_lists
                if task_list.id is not None
            }
        except ApiError as err:
            if err.status in AUTH_FAILED_STATUS:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="token_rotation_unauthorized",
                ) from err
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err

    async def _async_fetch_task_lists(self, space_id: str) -> list[TaskList]:
        """Fetch all chore and todo lists of the space, walking the pages."""
        task_lists: list[TaskList] = []
        for task_type in (TASK_TYPE_CHORES, TASK_TYPE_TODOS):
            page = 1
            while True:
                response = await self.tasks_api.get_task_lists_endpoint(
                    space_id=space_id,
                    task_type=task_type,
                    page=page,
                    page_size=PAGE_SIZE,
                    order_by="updated_at",
                    order="desc",
                )
                task_lists.extend(response.items or [])
                if page >= (response.total_pages or 1):
                    break
                page += 1
        return task_lists


class FamnShoppingCoordinator(DataUpdateCoordinator[dict[str, FamnShoppingList]]):
    """Coordinator fetching the space's shopping lists and open items."""

    config_entry: FamnConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: FamnConfigEntry, auth: FamnAuth
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_shopping",
            update_interval=SCAN_INTERVAL,
        )
        self.auth = auth
        self.list_api = ListApi(auth.client)
        self.list_item_api = ListItemApi(auth.client)

    @override
    async def _async_update_data(self) -> dict[str, FamnShoppingList]:
        """Fetch the shopping lists and their open items."""
        if TYPE_CHECKING:
            assert self.config_entry.unique_id is not None

        try:
            await self.auth.async_ensure_token_valid()
            lists = await self.list_api.get_lists_endpoint(
                space_id=self.config_entry.unique_id,
                list_type=SHOPPING_LIST_TYPES,
            )
            return {
                str(shopping_list.id): FamnShoppingList(
                    shopping_list=shopping_list,
                    items=await self.list_item_api.get_list_items_endpoint(
                        str(shopping_list.id)
                    ),
                )
                for shopping_list in lists
                if shopping_list.id is not None
            }
        except ApiError as err:
            if err.status in AUTH_FAILED_STATUS:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="token_rotation_unauthorized",
                ) from err
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err


@dataclass
class FamnRuntimeData:
    """Runtime data of a Famn config entry."""

    chores: FamnChoresCoordinator
    shopping: FamnShoppingCoordinator
