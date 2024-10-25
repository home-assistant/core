"""Actions for the Habitica integration."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from http import HTTPStatus
import logging
from typing import TYPE_CHECKING, Any
import uuid

from aiohttp import ClientResponseError
import voluptuous as vol

from homeassistant.components.todo import ATTR_DESCRIPTION, ATTR_RENAME
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DATE, ATTR_NAME, CONF_NAME
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.selector import ConfigEntrySelector

from .const import (
    ATTR_ADD_CHECKLIST_ITEM,
    ATTR_ALIAS,
    ATTR_ARGS,
    ATTR_CLEAR_DATE,
    ATTR_CLEAR_REMINDER,
    ATTR_CONFIG_ENTRY,
    ATTR_COST,
    ATTR_COUNTER_DOWN,
    ATTR_COUNTER_UP,
    ATTR_DATA,
    ATTR_DIRECTION,
    ATTR_ITEM,
    ATTR_FREQUENCY,
    ATTR_INTERVAL,
    ATTR_PATH,
    ATTR_PRIORITY,
    ATTR_REMINDER,
    ATTR_REMINDER_TIME,
    ATTR_REMOVE_CHECKLIST_ITEM,
    ATTR_REMOVE_REMINDER,
    ATTR_REMOVE_REMINDER_TIME,
    ATTR_REMOVE_TAG,
    ATTR_REPEAT,
    ATTR_REPEAT_MONTHLY,
    ATTR_SCORE_CHECKLIST_ITEM,
    ATTR_SKILL,
    ATTR_TARGET,
    ATTR_START_DATE,
    ATTR_STREAK,
    ATTR_TAG,
    ATTR_TASK,
    ATTR_UNSCORE_CHECKLIST_ITEM,
    ATTR_UP_DOWN,
    DOMAIN,
    EVENT_API_CALL_SUCCESS,
    PRIORITIES,
    SERVICE_ABORT_QUEST,
    SERVICE_ACCEPT_QUEST,
    SERVICE_API_CALL,
    SERVICE_CANCEL_QUEST,
    SERVICE_CAST_SKILL,
    SERVICE_LEAVE_QUEST,
    SERVICE_REJECT_QUEST,
    SERVICE_SCORE_HABIT,
    SERVICE_SCORE_REWARD,
    SERVICE_START_QUEST,
    SERVICE_TRANSFORMATION,
    SERVICE_UPDATE_DAILY,
    SERVICE_UPDATE_HABIT,
    SERVICE_UPDATE_REWARD,
    SERVICE_UPDATE_TODO,
    WEEK_DAYS,
)
from .types import HabiticaConfigEntry
from .util import lookup_task, to_date

_LOGGER = logging.getLogger(__name__)


SERVICE_API_CALL_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_NAME): str,
        vol.Required(ATTR_PATH): vol.All(cv.ensure_list, [str]),
        vol.Optional(ATTR_ARGS): dict,
    }
)

SERVICE_CAST_SKILL_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector(),
        vol.Required(ATTR_SKILL): cv.string,
        vol.Optional(ATTR_TASK): cv.string,
    }
)

SERVICE_MANAGE_QUEST_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector(),
    }
)
SERVICE_SCORE_TASK_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector(),
        vol.Required(ATTR_TASK): cv.string,
        vol.Optional(ATTR_DIRECTION): cv.string,
    }
)

SERVICE_TRANSFORMATION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector(),
        vol.Required(ATTR_ITEM): cv.string,
        vol.Required(ATTR_TARGET): cv.string,
    }
)

SERVICE_UPDATE_TASK_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector(),
        vol.Required(ATTR_TASK): cv.string,
        vol.Optional(ATTR_RENAME): cv.string,
        vol.Optional(ATTR_DESCRIPTION): cv.string,
        vol.Optional(ATTR_TAG): vol.All(cv.ensure_list, [str]),
        vol.Optional(ATTR_REMOVE_TAG): vol.All(cv.ensure_list, [str]),
        vol.Optional(ATTR_ALIAS): vol.All(
            cv.string, cv.matches_regex("^[a-zA-Z0-9-_]+$")
        ),
        vol.Optional(ATTR_PRIORITY): vol.All(cv.string, vol.In(set(PRIORITIES.keys()))),
        vol.Optional(ATTR_DATE): cv.date,
        vol.Optional(ATTR_CLEAR_DATE): cv.boolean,
        vol.Optional(ATTR_REMINDER): vol.All(cv.ensure_list, [cv.datetime]),
        vol.Optional(ATTR_REMINDER_TIME): vol.All(cv.ensure_list, [cv.time]),
        vol.Optional(ATTR_REMOVE_REMINDER): vol.All(cv.ensure_list, [cv.datetime]),
        vol.Optional(ATTR_REMOVE_REMINDER_TIME): vol.All(cv.ensure_list, [cv.time]),
        vol.Optional(ATTR_CLEAR_REMINDER): cv.boolean,
        vol.Optional(ATTR_COST): vol.Coerce(float),
        vol.Optional(ATTR_ADD_CHECKLIST_ITEM): vol.All(cv.ensure_list, [str]),
        vol.Optional(ATTR_REMOVE_CHECKLIST_ITEM): vol.All(cv.ensure_list, [str]),
        vol.Optional(ATTR_SCORE_CHECKLIST_ITEM): vol.All(cv.ensure_list, [str]),
        vol.Optional(ATTR_UNSCORE_CHECKLIST_ITEM): vol.All(cv.ensure_list, [str]),
        vol.Optional(ATTR_UP_DOWN): vol.All(
            cv.ensure_list, [vol.In({"positive", "negative"})]
        ),
        vol.Optional(ATTR_START_DATE): cv.date,
        vol.Optional(ATTR_FREQUENCY): vol.All(
            cv.string, vol.In({"daily", "weekly", "monthly", "yearly"})
        ),
        vol.Optional(ATTR_INTERVAL): int,
        vol.Optional(ATTR_REPEAT): vol.All(cv.ensure_list, [vol.In(WEEK_DAYS)]),
        vol.Optional(ATTR_REPEAT_MONTHLY): vol.All(
            cv.string, vol.In({"day_of_month", "day_of_week"})
        ),
        vol.Optional(ATTR_COUNTER_UP): int,
        vol.Optional(ATTR_COUNTER_DOWN): int,
        vol.Optional(ATTR_STREAK): int,
    }
)


def get_config_entry(hass: HomeAssistant, entry_id: str) -> HabiticaConfigEntry:
    """Return config entry or raise if not found or not loaded."""
    if not (entry := hass.config_entries.async_get_entry(entry_id)):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_found",
        )
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_loaded",
        )
    return entry


def async_setup_services(hass: HomeAssistant) -> None:  # noqa: C901
    """Set up services for Habitica integration."""

    async def handle_api_call(call: ServiceCall) -> None:
        async_create_issue(
            hass,
            DOMAIN,
            "deprecated_api_call",
            breaks_in_ha_version="2025.6.0",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_api_call",
        )
        _LOGGER.warning(
            "Deprecated action called: 'habitica.api_call' is deprecated and will be removed in Home Assistant version 2025.6.0"
        )

        name = call.data[ATTR_NAME]
        path = call.data[ATTR_PATH]
        entries = hass.config_entries.async_entries(DOMAIN)

        api = None
        for entry in entries:
            if entry.data[CONF_NAME] == name:
                api = entry.runtime_data.api
                break
        if api is None:
            _LOGGER.error("API_CALL: User '%s' not configured", name)
            return
        try:
            for element in path:
                api = api[element]
        except KeyError:
            _LOGGER.error(
                "API_CALL: Path %s is invalid for API on '{%s}' element", path, element
            )
            return
        kwargs = call.data.get(ATTR_ARGS, {})
        data = await api(**kwargs)
        hass.bus.async_fire(
            EVENT_API_CALL_SUCCESS, {ATTR_NAME: name, ATTR_PATH: path, ATTR_DATA: data}
        )

    async def cast_skill(call: ServiceCall) -> ServiceResponse:
        """Skill action."""
        entry = get_config_entry(hass, call.data[ATTR_CONFIG_ENTRY])
        coordinator = entry.runtime_data
        skill = {
            "pickpocket": {"spellId": "pickPocket", "cost": "10 MP"},
            "backstab": {"spellId": "backStab", "cost": "15 MP"},
            "smash": {"spellId": "smash", "cost": "10 MP"},
            "fireball": {"spellId": "fireball", "cost": "10 MP"},
        }
        try:
            task_id = next(
                task["id"]
                for task in coordinator.data.tasks
                if call.data[ATTR_TASK] in (task["id"], task.get("alias"))
                or call.data[ATTR_TASK] == task["text"]
            )
        except StopIteration as e:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="task_not_found",
                translation_placeholders={"task": f"'{call.data[ATTR_TASK]}'"},
            ) from e

        try:
            response: dict[str, Any] = await coordinator.api.user.class_.cast[
                skill[call.data[ATTR_SKILL]]["spellId"]
            ].post(targetId=task_id)
        except ClientResponseError as e:
            if e.status == HTTPStatus.TOO_MANY_REQUESTS:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="setup_rate_limit_exception",
                ) from e
            if e.status == HTTPStatus.UNAUTHORIZED:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="not_enough_mana",
                    translation_placeholders={
                        "cost": skill[call.data[ATTR_SKILL]]["cost"],
                        "mana": f"{int(coordinator.data.user.get("stats", {}).get("mp", 0))} MP",
                    },
                ) from e
            if e.status == HTTPStatus.NOT_FOUND:
                # could also be task not found, but the task is looked up
                # before the request, so most likely wrong skill selected
                # or the skill hasn't been unlocked yet.
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="skill_not_found",
                    translation_placeholders={"skill": call.data[ATTR_SKILL]},
                ) from e
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_call_exception",
            ) from e
        else:
            await coordinator.async_request_refresh()
            return response

    async def manage_quests(call: ServiceCall) -> ServiceResponse:
        """Accept, reject, start, leave or cancel quests."""
        entry = get_config_entry(hass, call.data[ATTR_CONFIG_ENTRY])
        coordinator = entry.runtime_data

        COMMAND_MAP = {
            SERVICE_ABORT_QUEST: "abort",
            SERVICE_ACCEPT_QUEST: "accept",
            SERVICE_CANCEL_QUEST: "cancel",
            SERVICE_LEAVE_QUEST: "leave",
            SERVICE_REJECT_QUEST: "reject",
            SERVICE_START_QUEST: "force-start",
        }
        try:
            return await coordinator.api.groups.party.quests[
                COMMAND_MAP[call.service]
            ].post()
        except ClientResponseError as e:
            if e.status == HTTPStatus.TOO_MANY_REQUESTS:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="setup_rate_limit_exception",
                ) from e
            if e.status == HTTPStatus.UNAUTHORIZED:
                raise ServiceValidationError(
                    translation_domain=DOMAIN, translation_key="quest_action_unallowed"
                ) from e
            if e.status == HTTPStatus.NOT_FOUND:
                raise ServiceValidationError(
                    translation_domain=DOMAIN, translation_key="quest_not_found"
                ) from e
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="service_call_exception"
            ) from e

    async def score_task(call: ServiceCall) -> ServiceResponse:
        """Score a task action."""
        entry = get_config_entry(hass, call.data[ATTR_CONFIG_ENTRY])
        coordinator = entry.runtime_data
        try:
            task_id, task_value = next(
                (task["id"], task.get("value"))
                for task in coordinator.data.tasks
                if call.data[ATTR_TASK] in (task["id"], task.get("alias"))
                or call.data[ATTR_TASK] == task["text"]
            )
        except StopIteration as e:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="task_not_found",
                translation_placeholders={"task": f"'{call.data[ATTR_TASK]}'"},
            ) from e

        try:
            response: dict[str, Any] = (
                await coordinator.api.tasks[task_id]
                .score[call.data.get(ATTR_DIRECTION, "up")]
                .post()
            )
        except ClientResponseError as e:
            if e.status == HTTPStatus.TOO_MANY_REQUESTS:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="setup_rate_limit_exception",
                ) from e
            if e.status == HTTPStatus.UNAUTHORIZED and task_value is not None:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="not_enough_gold",
                    translation_placeholders={
                        "gold": f"{coordinator.data.user["stats"]["gp"]:.2f} GP",
                        "cost": f"{task_value} GP",
                    },
                ) from e
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_call_exception",
            ) from e
        else:
            await coordinator.async_request_refresh()
            return response

    async def transformation(call: ServiceCall) -> ServiceResponse:
        """User a transformation item on a player character."""

        entry = get_config_entry(hass, call.data[ATTR_CONFIG_ENTRY])
        coordinator = entry.runtime_data
        ITEMID_MAP = {
            "snowball": {"itemId": "snowball"},
            "spooky_sparkles": {"itemId": "spookySparkles"},
            "seafoam": {"itemId": "seafoam"},
            "shiny_seed": {"itemId": "shinySeed"},
        }
        # check if target is self
        if call.data[ATTR_TARGET] in (
            coordinator.data.user["id"],
            coordinator.data.user["profile"]["name"],
            coordinator.data.user["auth"]["local"]["username"],
        ):
            target_id = coordinator.data.user["id"]
        else:
            # check if target is a party member
            try:
                party = await coordinator.api.groups.party.members.get()
            except ClientResponseError as e:
                if e.status == HTTPStatus.TOO_MANY_REQUESTS:
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="setup_rate_limit_exception",
                    ) from e
                if e.status == HTTPStatus.NOT_FOUND:
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="party_not_found",
                    ) from e
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="service_call_exception",
                ) from e
            try:
                target_id = next(
                    member["id"]
                    for member in party
                    if call.data[ATTR_TARGET].lower()
                    in (
                        member["id"],
                        member["auth"]["local"]["username"].lower(),
                        member["profile"]["name"].lower(),
                    )
                )
            except StopIteration as e:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="target_not_found",
                    translation_placeholders={"target": f"'{call.data[ATTR_TARGET]}'"},
                ) from e
        try:
            response: dict[str, Any] = await coordinator.api.user.class_.cast[
                ITEMID_MAP[call.data[ATTR_ITEM]]["itemId"]
            ].post(targetId=target_id)
        except ClientResponseError as e:
            if e.status == HTTPStatus.TOO_MANY_REQUESTS:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="setup_rate_limit_exception",
                ) from e
            if e.status == HTTPStatus.UNAUTHORIZED:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="item_not_found",
                    translation_placeholders={"item": call.data[ATTR_ITEM]},
                ) from e
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_call_exception",
            ) from e
        else:
            return response

    async def update_task(call: ServiceCall) -> ServiceResponse:  # noqa: C901
        """Update task action."""
        entry: HabiticaConfigEntry = get_config_entry(
            hass, call.data[ATTR_CONFIG_ENTRY]
        )
        coordinator = entry.runtime_data
        await coordinator.async_refresh()

        current_task = lookup_task(
            coordinator.data.tasks, call.data[ATTR_TASK], call.service
        )
        task_id = current_task["id"]
        data = {}

        if rename := call.data.get(ATTR_RENAME):
            data.update({"text": rename})

        if description := call.data.get(ATTR_DESCRIPTION):
            data.update({"notes": description})

        if priority := call.data.get(ATTR_PRIORITY):
            data.update({"priority": PRIORITIES[priority]})

        if due_date := call.data.get(ATTR_DATE):
            data.update({"date": (datetime.combine(due_date, time()).isoformat())})

        if call.data.get(ATTR_CLEAR_DATE):
            data.update({"date": None})

        tags = call.data.get(ATTR_TAG)
        remove_tags = call.data.get(ATTR_REMOVE_TAG)

        if tags or remove_tags:
            update_tags = set(
                next(
                    (
                        task.get("tags", [])
                        for task in coordinator.data.tasks
                        if task["id"] == task_id
                    ),
                    [],
                )
            )
            user_tags = {
                tag["name"].lower(): tag["id"]
                for tag in coordinator.data.user.get("tags", [])
            }

            if tags:
                # Creates new tag if it doesn't exist
                try:
                    update_tags.update(
                        {
                            user_tags.get(tag_name.lower())
                            or (await coordinator.api.tags.post(name=tag_name)).get(
                                "id"
                            )
                            for tag_name in tags
                        }
                    )
                except ClientResponseError as e:
                    if e.status == HTTPStatus.TOO_MANY_REQUESTS:
                        raise ServiceValidationError(
                            translation_domain=DOMAIN,
                            translation_key="setup_rate_limit_exception",
                        ) from e
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="service_call_exception",
                    ) from e

            if remove_tags:
                update_tags.difference_update(
                    {
                        user_tags[tag_name.lower()]
                        for tag_name in remove_tags
                        if tag_name.lower() in user_tags
                    }
                )

            data.update({"tags": list(update_tags)})

        if alias := call.data.get(ATTR_ALIAS):
            data.update({"alias": alias})

        if cost := call.data.get(ATTR_COST):
            data.update({"value": cost})

        add_checklist_item = call.data.get(ATTR_ADD_CHECKLIST_ITEM)
        remove_checklist_item = call.data.get(ATTR_REMOVE_CHECKLIST_ITEM)
        score_checklist_item = call.data.get(ATTR_SCORE_CHECKLIST_ITEM, [])
        unscore_checklist_item = call.data.get(ATTR_UNSCORE_CHECKLIST_ITEM, [])

        if (
            add_checklist_item
            or remove_checklist_item
            or score_checklist_item
            or unscore_checklist_item
        ):
            checklist = current_task.get("checklist", [])

            if add_checklist_item:
                checklist.extend(
                    {"completed": False, "id": str(uuid.uuid4()), "text": item}
                    for item in add_checklist_item
                    if not any(i["text"] == item for i in checklist)
                )
            if remove_checklist_item:
                checklist = [
                    item
                    for item in checklist
                    if item["text"] not in remove_checklist_item
                ]
            if score_checklist_item or unscore_checklist_item:
                checklist = [
                    {
                        **item,
                        "completed": (
                            True
                            if item["text"] in score_checklist_item
                            else False
                            if item["text"] in unscore_checklist_item
                            else item["completed"]
                        ),
                    }
                    for item in checklist
                ]

            data.update({"checklist": checklist})

        if frequency := call.data.get(ATTR_FREQUENCY):
            data.update({"frequency": frequency})
        if interval := call.data.get(ATTR_INTERVAL):
            data.update({"everyX": interval})
        if up_down := call.data.get(ATTR_UP_DOWN):
            data.update(
                {
                    "up": "positive" in up_down,
                    "down": "negative" in up_down,
                }
            )
        if start_date := call.data.get(ATTR_START_DATE):
            data.update(
                {"startDate": (datetime.combine(start_date, time()).isoformat())}
            )

        if repeat := call.data.get(ATTR_REPEAT):
            if (frequency or current_task.get("frequency")) == "weekly":
                data.update({"repeat": {d: d in repeat for d in WEEK_DAYS}})
            else:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="frequency_not_weekly",
                )
        if repeat_monthly := call.data.get(ATTR_REPEAT_MONTHLY):
            if (frequency or current_task.get("frequency")) != "monthly":
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="frequency_not_monthly",
                )

            current_start_date = start_date or to_date(current_task["startDate"])
            if not current_start_date:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="frequency_not_monthly",
                )

            if TYPE_CHECKING:
                assert isinstance(current_start_date, date)
            if repeat_monthly == "day_of_week":
                weekday = current_start_date.weekday()
                data.update(
                    {
                        "weeksOfMonth": (current_start_date.day - 1) // 7,
                        "repeat": {
                            day: i == weekday for i, day in enumerate(WEEK_DAYS)
                        },
                        "daysOfMonth": [],
                    }
                )
            else:
                data.update({"daysOfMonth": current_start_date.day, "weeksOfMonth": []})

        if reminder := call.data.get(ATTR_REMINDER):
            existing_reminder_datetimes = {
                datetime.fromisoformat(r["time"]).replace(tzinfo=None)
                for r in current_task.get("reminders", [])
            }

            data.update(
                {
                    "reminders": (
                        [
                            {
                                "id": str(uuid.uuid4()),
                                "time": r.isoformat(),
                            }
                            for r in reminder
                            if r not in existing_reminder_datetimes
                        ]
                        + current_task.get("reminders", [])
                    )
                }
            )
        if reminder_time := call.data.get(ATTR_REMINDER_TIME):
            existing_reminder_times = {
                datetime.fromisoformat(r["time"])
                .time()
                .replace(microsecond=0, second=0)
                for r in current_task.get("reminders", [])
            }

            data.update(
                {
                    "reminders": (
                        [
                            {
                                "id": str(uuid.uuid4()),
                                "startDate": "",
                                "time": datetime.combine(
                                    date.today(), r, tzinfo=UTC
                                ).isoformat(),
                            }
                            for r in reminder_time
                            if r not in existing_reminder_times
                        ]
                        + current_task.get("reminders", [])
                    )
                }
            )
        if remove_reminder := call.data.get(ATTR_REMOVE_REMINDER):
            reminders = list(
                filter(
                    lambda r: datetime.fromisoformat(r["time"]).replace(tzinfo=None)
                    not in remove_reminder,
                    current_task.get("reminders", []),
                )
            )
            data.update({"reminders": reminders})
        if remove_reminder_time := call.data.get(ATTR_REMOVE_REMINDER_TIME):
            reminders = list(
                filter(
                    lambda r: datetime.fromisoformat(r["time"])
                    .time()
                    .replace(second=0, microsecond=0)
                    not in remove_reminder_time,
                    current_task.get("reminders", []),
                )
            )
            data.update({"reminders": reminders})

        if call.data.get(ATTR_CLEAR_REMINDER):
            data.update({"reminders": []})

        if streak := call.data.get(ATTR_STREAK):
            data.update({"streak": streak})
        if counter_up := call.data.get(ATTR_COUNTER_UP):
            data.update({"counterUp": counter_up})
        if counter_down := call.data.get(ATTR_COUNTER_DOWN):
            data.update({"counterDown": counter_down})
        try:
            return await coordinator.api.tasks[task_id].put(**data)
        except ClientResponseError as e:
            if e.status == HTTPStatus.TOO_MANY_REQUESTS:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="setup_rate_limit_exception",
                ) from e
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_call_exception",
            ) from e

    for service in (
        SERVICE_ABORT_QUEST,
        SERVICE_ACCEPT_QUEST,
        SERVICE_CANCEL_QUEST,
        SERVICE_LEAVE_QUEST,
        SERVICE_REJECT_QUEST,
        SERVICE_START_QUEST,
    ):
        hass.services.async_register(
            DOMAIN,
            service,
            manage_quests,
            schema=SERVICE_MANAGE_QUEST_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )
    for service in (
        SERVICE_UPDATE_DAILY,
        SERVICE_UPDATE_HABIT,
        SERVICE_UPDATE_REWARD,
        SERVICE_UPDATE_TODO,
    ):
        hass.services.async_register(
            DOMAIN,
            service,
            update_task,
            schema=SERVICE_UPDATE_TASK_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )
    hass.services.async_register(
        DOMAIN,
        SERVICE_API_CALL,
        handle_api_call,
        schema=SERVICE_API_CALL_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CAST_SKILL,
        cast_skill,
        schema=SERVICE_CAST_SKILL_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SCORE_HABIT,
        score_task,
        schema=SERVICE_SCORE_TASK_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SCORE_REWARD,
        score_task,
        schema=SERVICE_SCORE_TASK_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_TRANSFORMATION,
        transformation,
        schema=SERVICE_TRANSFORMATION_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
