"""Actions for the Habitica integration."""

from dataclasses import asdict
from datetime import UTC, datetime, time
from enum import StrEnum
import logging
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID, uuid4

from aiohttp import ClientError
from habiticalib import (
    Checklist,
    Direction,
    Frequency,
    HabiticaException,
    NotAuthorizedError,
    NotFoundError,
    Reminders,
    Repeat,
    Skill,
    Task,
    TaskData,
    TaskPriority,
    TaskType,
    TooManyRequestsError,
)
import probatio

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.selector import ConfigEntrySelector
from homeassistant.util import dt as dt_util

from .const import DOMAIN, WEEK_DAYS
from .coordinator import HabiticaConfigEntry

_LOGGER = logging.getLogger(__name__)


class HabiticaService(StrEnum):
    """Store keys for Habitica services."""

    CAST_SKILL = "cast_skill"
    ACCEPT_QUEST = "accept_quest"
    REJECT_QUEST = "reject_quest"
    START_QUEST = "start_quest"
    CANCEL_QUEST = "cancel_quest"
    ABORT_QUEST = "abort_quest"
    LEAVE_QUEST = "leave_quest"
    SCORE_HABIT = "score_habit"
    SCORE_REWARD = "score_reward"
    TRANSFORMATION = "transformation"
    GET_TASKS = "get_tasks"
    UPDATE_REWARD = "update_reward"
    CREATE_REWARD = "create_reward"
    UPDATE_HABIT = "update_habit"
    CREATE_HABIT = "create_habit"
    UPDATE_TODO = "update_todo"
    CREATE_TODO = "create_todo"
    UPDATE_DAILY = "update_daily"
    CREATE_DAILY = "create_daily"


class HabiticaServiceArgument(StrEnum):
    """Store keys for Habitica service arguments."""

    CONFIG_ENTRY = "config_entry"
    SKILL = "skill"
    TASK = "task"
    DIRECTION = "direction"
    ITEM = "item"
    TARGET = "target"
    TYPE = "type"
    PRIORITY = "priority"
    TAG = "tag"
    KEYWORD = "keyword"
    RENAME = "rename"
    NOTES = "notes"
    COST = "cost"
    REMOVE_TAG = "remove_tag"
    ALIAS = "alias"
    NAME = "name"
    UP_DOWN = "up_down"
    FREQUENCY = "frequency"
    COUNTER_UP = "counter_up"
    COUNTER_DOWN = "counter_down"
    ADD_CHECKLIST_ITEM = "add_checklist_item"
    REMOVE_CHECKLIST_ITEM = "remove_checklist_item"
    SCORE_CHECKLIST_ITEM = "score_checklist_item"
    UNSCORE_CHECKLIST_ITEM = "unscore_checklist_item"
    COLLAPSE_CHECKLIST = "collapse_checklist"
    DATE = "date"
    CLEAR_DATE = "clear_date"
    REMINDER = "reminder"
    REMOVE_REMINDER = "remove_reminder"
    CLEAR_REMINDER = "clear_reminder"
    START_DATE = "start_date"
    EVERY_X = "every_x"
    REPEAT = "repeat"
    REPEAT_MONTHLY = "repeat_monthly"
    STREAK = "streak"


SERVICE_CAST_SKILL_SCHEMA = probatio.Schema(
    {
        probatio.Required(HabiticaServiceArgument.CONFIG_ENTRY): ConfigEntrySelector(
            {"integration": DOMAIN}
        ),
        probatio.Required(HabiticaServiceArgument.SKILL): cv.string,
        probatio.Optional(HabiticaServiceArgument.TASK): cv.string,
    }
)

SERVICE_MANAGE_QUEST_SCHEMA = probatio.Schema(
    {
        probatio.Required(HabiticaServiceArgument.CONFIG_ENTRY): ConfigEntrySelector(
            {"integration": DOMAIN}
        ),
    }
)
SERVICE_SCORE_TASK_SCHEMA = probatio.Schema(
    {
        probatio.Required(HabiticaServiceArgument.CONFIG_ENTRY): ConfigEntrySelector(
            {"integration": DOMAIN}
        ),
        probatio.Required(HabiticaServiceArgument.TASK): cv.string,
        probatio.Optional(HabiticaServiceArgument.DIRECTION): cv.string,
    }
)

SERVICE_TRANSFORMATION_SCHEMA = probatio.Schema(
    {
        probatio.Required(HabiticaServiceArgument.CONFIG_ENTRY): ConfigEntrySelector(
            {"integration": DOMAIN}
        ),
        probatio.Required(HabiticaServiceArgument.ITEM): cv.string,
        probatio.Required(HabiticaServiceArgument.TARGET): cv.string,
    }
)

COLLAPSE_CHECKLIST_MAP = {
    "collapsed": True,
    "expanded": False,
}

BASE_TASK_SCHEMA = probatio.Schema(
    {
        probatio.Required(HabiticaServiceArgument.CONFIG_ENTRY): ConfigEntrySelector(),
        probatio.Optional(HabiticaServiceArgument.RENAME): cv.string,
        probatio.Optional(HabiticaServiceArgument.NOTES): cv.string,
        probatio.Optional(HabiticaServiceArgument.TAG): probatio.All(
            probatio.EnsureList(), [str]
        ),
        probatio.Optional(HabiticaServiceArgument.ALIAS): probatio.All(
            cv.string, cv.matches_regex("^[a-zA-Z0-9-_]*$")
        ),
        probatio.Optional(HabiticaServiceArgument.COST): probatio.All(
            probatio.Coerce(float), probatio.Range(0)
        ),
        probatio.Optional(HabiticaServiceArgument.PRIORITY): probatio.All(
            probatio.Upper, probatio.In(TaskPriority._member_names_)
        ),
        probatio.Optional(HabiticaServiceArgument.UP_DOWN): probatio.All(
            probatio.EnsureList(), [str]
        ),
        probatio.Optional(HabiticaServiceArgument.COUNTER_UP): probatio.All(
            int, probatio.Range(0)
        ),
        probatio.Optional(HabiticaServiceArgument.COUNTER_DOWN): probatio.All(
            int, probatio.Range(0)
        ),
        probatio.Optional(HabiticaServiceArgument.FREQUENCY): probatio.Coerce(
            Frequency
        ),
        probatio.Optional(HabiticaServiceArgument.DATE): cv.date,
        probatio.Optional(HabiticaServiceArgument.CLEAR_DATE): cv.boolean,
        probatio.Optional(HabiticaServiceArgument.REMINDER): probatio.All(
            probatio.EnsureList(), [probatio.Any(cv.datetime, cv.time)]
        ),
        probatio.Optional(HabiticaServiceArgument.REMOVE_REMINDER): probatio.All(
            probatio.EnsureList(), [probatio.Any(cv.datetime, cv.time)]
        ),
        probatio.Optional(HabiticaServiceArgument.CLEAR_REMINDER): cv.boolean,
        probatio.Optional(HabiticaServiceArgument.ADD_CHECKLIST_ITEM): probatio.All(
            probatio.EnsureList(), [str]
        ),
        probatio.Optional(HabiticaServiceArgument.REMOVE_CHECKLIST_ITEM): probatio.All(
            probatio.EnsureList(), [str]
        ),
        probatio.Optional(HabiticaServiceArgument.SCORE_CHECKLIST_ITEM): probatio.All(
            probatio.EnsureList(), [str]
        ),
        probatio.Optional(HabiticaServiceArgument.UNSCORE_CHECKLIST_ITEM): probatio.All(
            probatio.EnsureList(), [str]
        ),
        probatio.Optional(HabiticaServiceArgument.COLLAPSE_CHECKLIST): probatio.In(
            COLLAPSE_CHECKLIST_MAP
        ),
        probatio.Optional(HabiticaServiceArgument.START_DATE): cv.date,
        probatio.Optional(HabiticaServiceArgument.EVERY_X): probatio.All(
            int, probatio.Range(0)
        ),
        probatio.Optional(HabiticaServiceArgument.REPEAT): probatio.All(
            probatio.EnsureList(), [probatio.In(WEEK_DAYS)]
        ),
        probatio.Optional(HabiticaServiceArgument.REPEAT_MONTHLY): probatio.All(
            cv.string, probatio.In({"day_of_month", "day_of_week"})
        ),
        probatio.Optional(HabiticaServiceArgument.STREAK): probatio.All(
            int, probatio.Range(0)
        ),
    }
)

SERVICE_UPDATE_TASK_SCHEMA = BASE_TASK_SCHEMA.extend(
    {
        probatio.Required(HabiticaServiceArgument.TASK): cv.string,
        probatio.Optional(HabiticaServiceArgument.REMOVE_TAG): probatio.All(
            probatio.EnsureList(), [str]
        ),
    }
)

SERVICE_CREATE_TASK_SCHEMA = BASE_TASK_SCHEMA.extend(
    {
        probatio.Required(HabiticaServiceArgument.NAME): cv.string,
    }
)

SERVICE_DAILY_SCHEMA = {
    probatio.Optional(HabiticaServiceArgument.REMINDER): probatio.All(
        probatio.EnsureList(), [cv.time]
    ),
    probatio.Optional(HabiticaServiceArgument.REMOVE_REMINDER): probatio.All(
        probatio.EnsureList(), [cv.time]
    ),
}


SERVICE_GET_TASKS_SCHEMA = probatio.Schema(
    {
        probatio.Required(HabiticaServiceArgument.CONFIG_ENTRY): ConfigEntrySelector(
            {"integration": DOMAIN}
        ),
        probatio.Optional(HabiticaServiceArgument.TYPE): probatio.All(
            probatio.EnsureList(),
            [probatio.All(probatio.Upper, probatio.In({x.name for x in TaskType}))],
        ),
        probatio.Optional(HabiticaServiceArgument.PRIORITY): probatio.All(
            probatio.EnsureList(),
            [probatio.All(probatio.Upper, probatio.In({x.name for x in TaskPriority}))],
        ),
        probatio.Optional(HabiticaServiceArgument.TASK): probatio.All(
            probatio.EnsureList(), [str]
        ),
        probatio.Optional(HabiticaServiceArgument.TAG): probatio.All(
            probatio.EnsureList(), [str]
        ),
        probatio.Optional(HabiticaServiceArgument.KEYWORD): cv.string,
    }
)

SKILL_MAP = {
    "pickpocket": Skill.PICKPOCKET,
    "backstab": Skill.BACKSTAB,
    "smash": Skill.BRUTAL_SMASH,
    "fireball": Skill.BURST_OF_FLAMES,
}
COST_MAP = {
    "pickpocket": "10 MP",
    "backstab": "15 MP",
    "smash": "10 MP",
    "fireball": "10 MP",
}
ITEMID_MAP = {
    "snowball": Skill.SNOWBALL,
    "spooky_sparkles": Skill.SPOOKY_SPARKLES,
    "seafoam": Skill.SEAFOAM,
    "shiny_seed": Skill.SHINY_SEED,
}


SERVICE_TASK_TYPE_MAP = {
    HabiticaService.UPDATE_REWARD: TaskType.REWARD,
    HabiticaService.CREATE_REWARD: TaskType.REWARD,
    HabiticaService.UPDATE_HABIT: TaskType.HABIT,
    HabiticaService.CREATE_HABIT: TaskType.HABIT,
    HabiticaService.UPDATE_TODO: TaskType.TODO,
    HabiticaService.CREATE_TODO: TaskType.TODO,
    HabiticaService.UPDATE_DAILY: TaskType.DAILY,
    HabiticaService.CREATE_DAILY: TaskType.DAILY,
}


async def _cast_skill(call: ServiceCall) -> ServiceResponse:
    """Skill action."""
    entry: HabiticaConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[HabiticaServiceArgument.CONFIG_ENTRY]
    )
    coordinator = entry.runtime_data

    skill = SKILL_MAP[call.data[HabiticaServiceArgument.SKILL]]
    cost = COST_MAP[call.data[HabiticaServiceArgument.SKILL]]

    try:
        task_id = next(
            task.id
            for task in coordinator.data.tasks
            if call.data[HabiticaServiceArgument.TASK]
            in (str(task.id), task.alias, task.text)
        )
    except StopIteration as e:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="task_not_found",
            translation_placeholders={
                "task": f"'{call.data[HabiticaServiceArgument.TASK]}'"
            },
        ) from e

    try:
        response = await coordinator.habitica.cast_skill(skill, task_id)
    except TooManyRequestsError as e:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="setup_rate_limit_exception",
            translation_placeholders={"retry_after": str(e.retry_after)},
        ) from e
    except NotAuthorizedError as e:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_enough_mana",
            translation_placeholders={
                "cost": cost,
                "mana": f"{int(coordinator.data.user.stats.mp or 0)} MP",
            },
        ) from e
    except NotFoundError as e:
        # could also be task not found, but the task is looked up
        # before the request, so most likely wrong skill selected
        # or the skill hasn't been unlocked yet.
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="skill_not_found",
            translation_placeholders={
                "skill": call.data[HabiticaServiceArgument.SKILL]
            },
        ) from e
    except HabiticaException as e:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_call_exception",
            translation_placeholders={"reason": str(e.error.message)},
        ) from e
    except ClientError as e:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_call_exception",
            translation_placeholders={"reason": str(e)},
        ) from e
    else:
        await coordinator.async_request_refresh()
        return asdict(response.data) if call.return_response is True else None


async def _manage_quests(call: ServiceCall) -> ServiceResponse:
    """Accept, reject, start, leave or cancel quests."""
    entry: HabiticaConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[HabiticaServiceArgument.CONFIG_ENTRY]
    )
    coordinator = entry.runtime_data

    func_map = {
        HabiticaService.ABORT_QUEST: coordinator.habitica.abort_quest,
        HabiticaService.ACCEPT_QUEST: coordinator.habitica.accept_quest,
        HabiticaService.CANCEL_QUEST: coordinator.habitica.cancel_quest,
        HabiticaService.LEAVE_QUEST: coordinator.habitica.leave_quest,
        HabiticaService.REJECT_QUEST: coordinator.habitica.reject_quest,
        HabiticaService.START_QUEST: coordinator.habitica.start_quest,
    }

    func = func_map[HabiticaService(call.service)]

    try:
        response = await func()
    except TooManyRequestsError as e:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="setup_rate_limit_exception",
            translation_placeholders={"retry_after": str(e.retry_after)},
        ) from e
    except NotAuthorizedError as e:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="quest_action_unallowed"
        ) from e
    except NotFoundError as e:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="quest_not_found"
        ) from e
    except HabiticaException as e:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_call_exception",
            translation_placeholders={"reason": str(e.error.message)},
        ) from e
    except ClientError as e:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_call_exception",
            translation_placeholders={"reason": str(e)},
        ) from e
    else:
        return asdict(response.data) if call.return_response is True else None


async def _score_task(call: ServiceCall) -> ServiceResponse:
    """Score a task action."""
    entry: HabiticaConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[HabiticaServiceArgument.CONFIG_ENTRY]
    )
    coordinator = entry.runtime_data

    direction = (
        Direction.DOWN
        if call.data.get(HabiticaServiceArgument.DIRECTION) == "down"
        else Direction.UP
    )
    try:
        task_id, task_value = next(
            (task.id, task.value)
            for task in coordinator.data.tasks
            if call.data[HabiticaServiceArgument.TASK]
            in (str(task.id), task.alias, task.text)
        )
    except StopIteration as e:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="task_not_found",
            translation_placeholders={
                "task": f"'{call.data[HabiticaServiceArgument.TASK]}'"
            },
        ) from e

    if TYPE_CHECKING:
        assert task_id
    try:
        response = await coordinator.habitica.update_score(task_id, direction)
    except TooManyRequestsError as e:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="setup_rate_limit_exception",
            translation_placeholders={"retry_after": str(e.retry_after)},
        ) from e
    except NotAuthorizedError as e:
        if task_value is not None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_enough_gold",
                translation_placeholders={
                    "gold": f"{(coordinator.data.user.stats.gp or 0):.2f} GP",
                    "cost": f"{task_value:.2f} GP",
                },
            ) from e
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_call_exception",
            translation_placeholders={"reason": e.error.message},
        ) from e
    except HabiticaException as e:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_call_exception",
            translation_placeholders={"reason": str(e.error.message)},
        ) from e
    except ClientError as e:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_call_exception",
            translation_placeholders={"reason": str(e)},
        ) from e
    else:
        await coordinator.async_request_refresh()
        return asdict(response.data) if call.return_response is True else None


async def _transformation(call: ServiceCall) -> ServiceResponse:
    """User a transformation item on a player character."""

    entry: HabiticaConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[HabiticaServiceArgument.CONFIG_ENTRY]
    )
    coordinator = entry.runtime_data

    item = ITEMID_MAP[call.data[HabiticaServiceArgument.ITEM]]
    # check if target is self
    if call.data[HabiticaServiceArgument.TARGET] in (
        str(coordinator.data.user.id),
        coordinator.data.user.profile.name,
        coordinator.data.user.auth.local.username,
    ):
        target_id = coordinator.data.user.id
    else:
        # check if target is a party member
        try:
            party = await coordinator.habitica.get_group_members(public_fields=True)
        except NotFoundError as e:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="party_not_found",
            ) from e
        except HabiticaException as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_call_exception",
                translation_placeholders={"reason": str(e.error.message)},
            ) from e
        except ClientError as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_call_exception",
                translation_placeholders={"reason": str(e)},
            ) from e
        try:
            target_id = next(
                member.id
                for member in party.data
                if member.id
                and call.data[HabiticaServiceArgument.TARGET].lower()
                in (
                    str(member.id),
                    str(member.auth.local.username).lower(),
                    str(member.profile.name).lower(),
                )
            )
        except StopIteration as e:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="target_not_found",
                translation_placeholders={
                    "target": f"'{call.data[HabiticaServiceArgument.TARGET]}'"
                },
            ) from e
    try:
        response = await coordinator.habitica.cast_skill(item, target_id)
    except TooManyRequestsError as e:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="setup_rate_limit_exception",
            translation_placeholders={"retry_after": str(e.retry_after)},
        ) from e
    except NotAuthorizedError as e:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="item_not_found",
            translation_placeholders={"item": call.data[HabiticaServiceArgument.ITEM]},
        ) from e
    except HabiticaException as e:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_call_exception",
            translation_placeholders={"reason": str(e.error.message)},
        ) from e
    except ClientError as e:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_call_exception",
            translation_placeholders={"reason": str(e)},
        ) from e
    else:
        return asdict(response.data) if call.return_response is True else None


async def _get_tasks(call: ServiceCall) -> ServiceResponse:
    """Get tasks action."""

    entry: HabiticaConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[HabiticaServiceArgument.CONFIG_ENTRY]
    )
    coordinator = entry.runtime_data
    response: list[TaskData] = coordinator.data.tasks

    if types := {TaskType[x] for x in call.data.get(HabiticaServiceArgument.TYPE, [])}:
        response = [task for task in response if task.Type in types]

    if priority := {
        TaskPriority[x] for x in call.data.get(HabiticaServiceArgument.PRIORITY, [])
    }:
        response = [task for task in response if task.priority in priority]

    if tasks := call.data.get(HabiticaServiceArgument.TASK):
        response = [
            task
            for task in response
            if str(task.id) in tasks or task.alias in tasks or task.text in tasks
        ]

    if tags := call.data.get(HabiticaServiceArgument.TAG):
        tag_ids = {
            tag.id
            for tag in coordinator.data.user.tags
            if (tag.name and tag.name.lower())
            in (tag.lower() for tag in tags)  # Case-insensitive matching
            and tag.id
        }

        response = [
            task
            for task in response
            if any(tag_id in task.tags for tag_id in tag_ids if task.tags)
        ]
    if keyword := call.data.get(HabiticaServiceArgument.KEYWORD):
        keyword = keyword.lower()
        response = [
            task
            for task in response
            if (task.text and keyword in task.text.lower())
            or (task.notes and keyword in task.notes.lower())
            or any(keyword in item.text.lower() for item in task.checklist)
        ]
    result: dict[str, Any] = {
        "tasks": [task.to_dict(omit_none=False) for task in response]
    }

    return result


async def _create_or_update_task(call: ServiceCall) -> ServiceResponse:  # noqa: C901
    """Create or update task action."""
    entry: HabiticaConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[HabiticaServiceArgument.CONFIG_ENTRY]
    )
    coordinator = entry.runtime_data
    await coordinator.async_refresh()
    is_update = call.service in (
        HabiticaService.UPDATE_HABIT,
        HabiticaService.UPDATE_REWARD,
        HabiticaService.UPDATE_TODO,
        HabiticaService.UPDATE_DAILY,
    )
    task_type = SERVICE_TASK_TYPE_MAP[HabiticaService(call.service)]
    current_task = None

    if is_update:
        try:
            current_task = next(
                task
                for task in coordinator.data.tasks
                if call.data[HabiticaServiceArgument.TASK]
                in (str(task.id), task.alias, task.text)
                and task.Type is task_type
            )
        except StopIteration as e:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="task_not_found",
                translation_placeholders={
                    "task": f"'{call.data[HabiticaServiceArgument.TASK]}'"
                },
            ) from e

    data = Task()

    if not is_update:
        data["type"] = task_type

    if (text := call.data.get(HabiticaServiceArgument.RENAME)) or (
        text := call.data.get(HabiticaServiceArgument.NAME)
    ):
        data["text"] = text

    if (notes := call.data.get(HabiticaServiceArgument.NOTES)) is not None:
        data["notes"] = notes

    tags = cast(list[str], call.data.get(HabiticaServiceArgument.TAG))
    remove_tags = cast(list[str], call.data.get(HabiticaServiceArgument.REMOVE_TAG))

    if tags or remove_tags:
        update_tags = set(current_task.tags) if current_task else set()
        user_tags = {
            tag.name.lower(): tag.id
            for tag in coordinator.data.user.tags
            if tag.id and tag.name
        }

        if tags:
            # Creates new tag if it doesn't exist
            async def create_tag(tag_name: str) -> UUID:
                tag_id = (await coordinator.habitica.create_tag(tag_name)).data.id
                if TYPE_CHECKING:
                    assert tag_id
                return tag_id

            try:
                update_tags.update(
                    {
                        user_tags.get(tag_name.lower()) or (await create_tag(tag_name))
                        for tag_name in tags
                    }
                )
            except TooManyRequestsError as e:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="setup_rate_limit_exception",
                    translation_placeholders={"retry_after": str(e.retry_after)},
                ) from e
            except HabiticaException as e:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="service_call_exception",
                    translation_placeholders={"reason": str(e.error.message)},
                ) from e
            except ClientError as e:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="service_call_exception",
                    translation_placeholders={"reason": str(e)},
                ) from e

        if remove_tags:
            update_tags.difference_update(
                {
                    user_tags[tag_name.lower()]
                    for tag_name in remove_tags
                    if tag_name.lower() in user_tags
                }
            )

        data["tags"] = list(update_tags)

    if (alias := call.data.get(HabiticaServiceArgument.ALIAS)) is not None:
        data["alias"] = alias

    if (cost := call.data.get(HabiticaServiceArgument.COST)) is not None:
        data["value"] = cost

    if priority := call.data.get(HabiticaServiceArgument.PRIORITY):
        data["priority"] = TaskPriority[priority]

    if frequency := call.data.get(HabiticaServiceArgument.FREQUENCY):
        data["frequency"] = frequency
    else:
        frequency = current_task.frequency if current_task else Frequency.WEEKLY

    if up_down := call.data.get(HabiticaServiceArgument.UP_DOWN):
        data["up"] = "up" in up_down
        data["down"] = "down" in up_down

    if counter_up := call.data.get(HabiticaServiceArgument.COUNTER_UP):
        data["counterUp"] = counter_up

    if counter_down := call.data.get(HabiticaServiceArgument.COUNTER_DOWN):
        data["counterDown"] = counter_down

    if due_date := call.data.get(HabiticaServiceArgument.DATE):
        data["date"] = datetime.combine(due_date, time())

    if call.data.get(HabiticaServiceArgument.CLEAR_DATE):
        data["date"] = None

    checklist = current_task.checklist if current_task else []

    if add_checklist_item := call.data.get(HabiticaServiceArgument.ADD_CHECKLIST_ITEM):
        checklist.extend(
            Checklist(completed=False, id=uuid4(), text=item)
            for item in add_checklist_item
            if not any(i.text == item for i in checklist)
        )
    if remove_checklist_item := call.data.get(
        HabiticaServiceArgument.REMOVE_CHECKLIST_ITEM
    ):
        checklist = [
            item for item in checklist if item.text not in remove_checklist_item
        ]

    if score_checklist_item := call.data.get(
        HabiticaServiceArgument.SCORE_CHECKLIST_ITEM
    ):
        for item in checklist:
            if item.text in score_checklist_item:
                item.completed = True

    if unscore_checklist_item := call.data.get(
        HabiticaServiceArgument.UNSCORE_CHECKLIST_ITEM
    ):
        for item in checklist:
            if item.text in unscore_checklist_item:
                item.completed = False
    if (
        add_checklist_item
        or remove_checklist_item
        or score_checklist_item
        or unscore_checklist_item
    ):
        data["checklist"] = checklist

    if collapse_checklist := call.data.get(HabiticaServiceArgument.COLLAPSE_CHECKLIST):
        data["collapseChecklist"] = COLLAPSE_CHECKLIST_MAP[collapse_checklist]

    reminders = current_task.reminders if current_task else []

    if add_reminders := call.data.get(HabiticaServiceArgument.REMINDER):
        if task_type is TaskType.TODO:
            existing_reminder_datetimes = {
                r.time.replace(tzinfo=None) for r in reminders
            }

            reminders.extend(
                Reminders(id=uuid4(), time=r)
                for r in add_reminders
                if r not in existing_reminder_datetimes
            )
        if task_type is TaskType.DAILY:
            existing_reminder_times = {
                r.time.time().replace(microsecond=0, second=0) for r in reminders
            }

            reminders.extend(
                Reminders(
                    id=uuid4(),
                    time=datetime.combine(dt_util.now().date(), r, tzinfo=UTC),
                )
                for r in add_reminders
                if r not in existing_reminder_times
            )

    if remove_reminder := call.data.get(HabiticaServiceArgument.REMOVE_REMINDER):
        if task_type is TaskType.TODO:
            reminders = list(
                filter(
                    lambda r: r.time.replace(tzinfo=None) not in remove_reminder,
                    reminders,
                )
            )
        if task_type is TaskType.DAILY:
            reminders = list(
                filter(
                    lambda r: (
                        r.time.time().replace(second=0, microsecond=0)
                        not in remove_reminder
                    ),
                    reminders,
                )
            )

    if clear_reminders := call.data.get(HabiticaServiceArgument.CLEAR_REMINDER):
        reminders = []

    if add_reminders or remove_reminder or clear_reminders:
        data["reminders"] = reminders

    if start_date := call.data.get(HabiticaServiceArgument.START_DATE):
        data["startDate"] = datetime.combine(start_date, time())
    else:
        start_date = (
            current_task.startDate
            if current_task and current_task.startDate
            else dt_util.start_of_local_day()
        )
    if repeat := call.data.get(HabiticaServiceArgument.REPEAT):
        if frequency is Frequency.WEEKLY:
            data["repeat"] = Repeat(**{d: d in repeat for d in WEEK_DAYS})
        else:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="frequency_not_weekly",
            )
    if repeat_monthly := call.data.get(HabiticaServiceArgument.REPEAT_MONTHLY):
        if frequency is not Frequency.MONTHLY:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="frequency_not_monthly",
            )

        if repeat_monthly == "day_of_week":
            weekday = start_date.weekday()
            data["weeksOfMonth"] = [(start_date.day - 1) // 7]
            data["repeat"] = Repeat(
                **{day: i == weekday for i, day in enumerate(WEEK_DAYS)}
            )
            data["daysOfMonth"] = []

        else:
            data["daysOfMonth"] = [start_date.day]
            data["weeksOfMonth"] = []

    if (interval := call.data.get(HabiticaServiceArgument.EVERY_X)) is not None:
        data["everyX"] = interval

    if (streak := call.data.get(HabiticaServiceArgument.STREAK)) is not None:
        data["streak"] = streak

    try:
        if is_update:
            if TYPE_CHECKING:
                assert current_task
                assert current_task.id
            response = await coordinator.habitica.update_task(current_task.id, data)
        else:
            response = await coordinator.habitica.create_task(data)
    except TooManyRequestsError as e:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="setup_rate_limit_exception",
            translation_placeholders={"retry_after": str(e.retry_after)},
        ) from e
    except HabiticaException as e:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_call_exception",
            translation_placeholders={"reason": str(e.error.message)},
        ) from e
    except ClientError as e:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_call_exception",
            translation_placeholders={"reason": str(e)},
        ) from e
    else:
        return (
            response.data.to_dict(omit_none=True)
            if call.return_response is True
            else None
        )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Habitica integration."""

    for service_name in (
        HabiticaService.ABORT_QUEST,
        HabiticaService.ACCEPT_QUEST,
        HabiticaService.CANCEL_QUEST,
        HabiticaService.LEAVE_QUEST,
        HabiticaService.REJECT_QUEST,
        HabiticaService.START_QUEST,
    ):
        hass.services.async_register(
            DOMAIN,
            service_name,
            _manage_quests,
            schema=SERVICE_MANAGE_QUEST_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )

    for service_name in (
        HabiticaService.UPDATE_DAILY,
        HabiticaService.UPDATE_HABIT,
        HabiticaService.UPDATE_REWARD,
        HabiticaService.UPDATE_TODO,
    ):
        hass.services.async_register(
            DOMAIN,
            service_name,
            _create_or_update_task,
            schema=SERVICE_UPDATE_TASK_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )
    for service_name in (
        HabiticaService.CREATE_DAILY,
        HabiticaService.CREATE_HABIT,
        HabiticaService.CREATE_REWARD,
        HabiticaService.CREATE_TODO,
    ):
        hass.services.async_register(
            DOMAIN,
            service_name,
            _create_or_update_task,
            schema=SERVICE_CREATE_TASK_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )

    hass.services.async_register(
        DOMAIN,
        HabiticaService.CAST_SKILL,
        _cast_skill,
        schema=SERVICE_CAST_SKILL_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    hass.services.async_register(
        DOMAIN,
        HabiticaService.SCORE_HABIT,
        _score_task,
        schema=SERVICE_SCORE_TASK_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        HabiticaService.SCORE_REWARD,
        _score_task,
        schema=SERVICE_SCORE_TASK_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    hass.services.async_register(
        DOMAIN,
        HabiticaService.TRANSFORMATION,
        _transformation,
        schema=SERVICE_TRANSFORMATION_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        HabiticaService.GET_TASKS,
        _get_tasks,
        schema=SERVICE_GET_TASKS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
