"""DataUpdateCoordinators for the Famn integration."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, override

from famn_sdk import (
    ApiError,
    Calendar,
    CalendarApi,
    CalendarEvent,
    LeaderboardEntry,
    ListApi,
    ListItem,
    ListItemApi,
    ListModel,
    MealPlannerApi,
    MealSlot,
    SpaceApi,
    SpaceMember,
    SpaceSeasonSummary,
    TaskItem,
    TaskList,
    TasksApi,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import AUTH_FAILED_STATUS, FamnAuth
from .const import DOMAIN, LOGGER, TASK_TYPE_CHORES, TASK_TYPE_TODOS

# The realtime gateway pushes changes as they happen; polling stays on as
# a fallback for events missed while the WebSocket was down.
SCAN_INTERVAL = timedelta(minutes=15)

PAGE_SIZE = 100

# How far ahead the calendars coordinator fetches occurrences for the "next
# event" shown on calendar entities. On-demand range queries (the calendar
# card) are not limited by this.
CALENDAR_LOOKAHEAD = timedelta(days=30)

# The Famn list types that behave like shopping lists; the same service also
# stores freezer/pantry inventories, which make no sense as todo entities.
SHOPPING_LIST_TYPES = ["grocery", "shopping"]

# How far ahead the meal plan is fetched; enough for "tonight" and a week
# view on a dashboard.
MEAL_PLAN_LOOKAHEAD = timedelta(days=7)

type FamnConfigEntry = ConfigEntry[FamnRuntimeData]


@dataclass(frozen=True)
class FamnChoreList:
    """A Famn chore list together with its open items."""

    task_list: TaskList
    items: list[TaskItem]


@dataclass(frozen=True)
class FamnCalendarData:
    """A Famn calendar together with its upcoming occurrences."""

    calendar: Calendar
    upcoming: list[CalendarEvent]


@dataclass(frozen=True)
class FamnScoreData:
    """The space's member roster, XP leaderboard, and current season."""

    members: list[SpaceMember]
    leaderboard: list[LeaderboardEntry]
    season: SpaceSeasonSummary


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
        await self.auth.async_ensure_token_valid()

        if TYPE_CHECKING:
            assert self.config_entry.unique_id is not None

        try:
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


class FamnCalendarsCoordinator(DataUpdateCoordinator[dict[str, FamnCalendarData]]):
    """Coordinator fetching the calendars of the paired space.

    Each refresh also fetches the expanded occurrences of the near future,
    which is what the calendar entities show as their current/next event.
    """

    config_entry: FamnConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: FamnConfigEntry, auth: FamnAuth
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_calendars",
            update_interval=SCAN_INTERVAL,
        )
        self.auth = auth
        self.calendar_api = CalendarApi(auth.client)

    @override
    async def _async_update_data(self) -> dict[str, FamnCalendarData]:
        """Fetch the calendars and their upcoming occurrences."""
        await self.auth.async_ensure_token_valid()

        if TYPE_CHECKING:
            assert self.config_entry.unique_id is not None

        now = dt_util.utcnow()
        try:
            calendars = await self._async_fetch_calendars(self.config_entry.unique_id)
            return {
                str(calendar.id): FamnCalendarData(
                    calendar=calendar,
                    upcoming=await self.calendar_api.get_calendar_events_endpoint(
                        str(calendar.id),
                        from_=now.isoformat(),
                        to=(now + CALENDAR_LOOKAHEAD).isoformat(),
                        expand=True,
                    ),
                )
                for calendar in calendars
                if calendar.id is not None
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

    async def _async_fetch_calendars(self, space_id: str) -> list[Calendar]:
        """Fetch all calendars of the space, walking the pages."""
        calendars: list[Calendar] = []
        page = 1
        while True:
            response = await self.calendar_api.get_calendars_endpoint(
                space_id=space_id,
                page=page,
                page_size=PAGE_SIZE,
            )
            calendars.extend(response.items or [])
            if page >= (response.total_pages or 1):
                return calendars
            page += 1

    async def async_get_events_between(
        self, calendar_id: str, start: datetime, end: datetime
    ) -> list[CalendarEvent]:
        """Fetch the expanded occurrences of one calendar within a range.

        Raises `ApiError`, so callers map failures onto their own context.
        """
        await self.auth.async_ensure_token_valid()
        return await self.calendar_api.get_calendar_events_endpoint(
            calendar_id,
            from_=start.isoformat(),
            to=end.isoformat(),
            expand=True,
        )


class FamnScoresCoordinator(DataUpdateCoordinator[FamnScoreData]):
    """Coordinator fetching the space's XP leaderboard.

    The leaderboard embeds member display names, so no separate member
    lookup is needed. Members without XP this season are absent from it —
    Famn's seasons reset weekly.
    """

    config_entry: FamnConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: FamnConfigEntry, auth: FamnAuth
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_scores",
            update_interval=SCAN_INTERVAL,
        )
        self.auth = auth
        self.space_api = SpaceApi(auth.client)

    @override
    async def _async_update_data(self) -> FamnScoreData:
        """Fetch the leaderboard and season summary."""
        await self.auth.async_ensure_token_valid()

        if TYPE_CHECKING:
            assert self.config_entry.unique_id is not None
        space_id = self.config_entry.unique_id

        try:
            return FamnScoreData(
                members=await self.space_api.get_space_members_endpoint(space_id),
                leaderboard=await self.space_api.get_space_score_leaderboard_endpoint(
                    space_id, limit=50
                ),
                season=await self.space_api.get_space_score_season_endpoint(space_id),
            )
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
        await self.auth.async_ensure_token_valid()

        if TYPE_CHECKING:
            assert self.config_entry.unique_id is not None

        try:
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


class FamnMealPlanCoordinator(DataUpdateCoordinator[list[MealSlot]]):
    """Coordinator fetching the space's meal plan for the coming week.

    Recipes are embedded in the slots, so tonight's dinner needs no
    further lookups.
    """

    config_entry: FamnConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: FamnConfigEntry, auth: FamnAuth
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_meal_plan",
            update_interval=SCAN_INTERVAL,
        )
        self.auth = auth
        self.meal_planner_api = MealPlannerApi(auth.client)

    @override
    async def _async_update_data(self) -> list[MealSlot]:
        """Fetch the meal slots for the coming week."""
        await self.auth.async_ensure_token_valid()

        if TYPE_CHECKING:
            assert self.config_entry.unique_id is not None

        today = dt_util.now().date()
        try:
            response = await self.meal_planner_api.get_meal_slots_endpoint(
                space_id=self.config_entry.unique_id,
                from_date=today.isoformat(),
                to_date=(today + MEAL_PLAN_LOOKAHEAD).isoformat(),
                page_size=100,
            )
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
        return list(response.items or [])


@dataclass
class FamnRuntimeData:
    """Runtime data of a Famn config entry."""

    chores: FamnChoresCoordinator
    calendars: FamnCalendarsCoordinator
    scores: FamnScoresCoordinator
    shopping: FamnShoppingCoordinator
    meals: FamnMealPlanCoordinator
