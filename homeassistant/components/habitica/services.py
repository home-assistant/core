"""Actions for the Habitica integration."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, date, datetime, time
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
import voluptuous as vol

from homeassistant.components.todo import ATTR_RENAME
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DATE, ATTR_NAME
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import ConfigEntrySelector
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_ADD_CHECKLIST_ITEM,
    ATTR_ALIAS,
    ATTR_CLEAR_DATE,
    ATTR_CLEAR_REMINDER,
    ATTR_CONFIG_ENTRY,
    ATTR_COST,
    ATTR_COUNTER_DOWN,
    ATTR_COUNTER_UP,
    ATTR_DIRECTION,
    ATTR_FREQUENCY,
    ATTR_INTERVAL,
    ATTR_ITEM,
    ATTR_KEYWORD,
    ATTR_NOTES,
    ATTR_PRIORITY,
    ATTR_REMINDER,
    ATTR_REMOVE_CHECKLIST_ITEM,
    ATTR_REMOVE_REMINDER,
    ATTR_REMOVE_TAG,
    ATTR_REPEAT,
    ATTR_REPEAT_MONTHLY,
    ATTR_SCORE_CHECKLIST_ITEM,
    ATTR_SKILL,
    ATTR_START_DATE,
    ATTR_STREAK,
    ATTR_TAG,
    ATTR_TARGET,
    ATTR_TASK,
    ATTR_TYPE,
    ATTR_UNSCORE_CHECKLIST_ITEM,
    ATTR_UP_DOWN,
    DOMAIN,
    SERVICE_ABORT_QUEST,
    SERVICE_ACCEPT_QUEST,
    SERVICE_CANCEL_QUEST,
    SERVICE_CAST_SKILL,
    SERVICE_CREATE_DAILY,
    SERVICE_CREATE_HABIT,
    SERVICE_CREATE_REWARD,
    SERVICE_CREATE_TODO,
    SERVICE_GET_TASKS,
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
from .coordinator import HabiticaConfigEntry

_LOGGER = logging.getLogger(__name__)


SERVICE_CAST_SKILL_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector({"integration": DOMAIN}),
        vol.Required(ATTR_SKILL): cv.string,
        vol.Optional(ATTR_TASK): cv.string,
    }
)

SERVICE_MANAGE_QUEST_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector({"integration": DOMAIN}),
    }
)
SERVICE_SCORE_TASK_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector({"integration": DOMAIN}),
        vol.Required(ATTR_TASK): cv.string,
        vol.Optional(ATTR_DIRECTION): cv.string,
    }
)

SERVICE_TRANSFORMATION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector({"integration": DOMAIN}),
        vol.Required(ATTR_ITEM): cv.string,
        vol.Required(ATTR_TARGET): cv.string,
    }
)

BASE_TASK_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector(),
        vol.Optional(ATTR_RENAME): cv.string,
        vol.Optional(ATTR_NOTES): cv.string,
        vol.Optional(ATTR_TAG): vol.All(cv.ensure_list, [str]),
        vol.Optional(ATTR_ALIAS): vol.All(
            cv.string, cv.matches_regex("^[a-zA-Z0-9-_]*$")
        ),
        vol.Optional(ATTR_COST): vol.All(vol.Coerce(float), vol.Range(0)),
        vol.Optional(ATTR_PRIORITY): vol.All(
            vol.Upper, vol.In(TaskPriority._member_names_)
        ),
        vol.Optional(ATTR_UP_DOWN): vol.All(cv.ensure_list, [str]),
        vol.Optional(ATTR_COUNTER_UP): vol.All(int, vol.Range(0)),
        vol.Optional(ATTR_COUNTER_DOWN): vol.All(int, vol.Range(0)),
        vol.Optional(ATTR_FREQUENCY): vol.Coerce(Frequency),
        vol.Optional(ATTR_DATE): cv.date,
        vol.Optional(ATTR_CLEAR_DATE): cv.boolean,
        vol.Optional(ATTR_REMINDER): vol.All(
            cv.ensure_list, [vol.Any(cv.datetime, cv.time)]
        ),
        vol.Optional(ATTR_REMOVE_REMINDER): vol.All(
            cv.ensure_list, [vol.Any(cv.datetime, cv.time)]
        ),
        vol.Optional(ATTR_CLEAR_REMINDER): cv.boolean,
        vol.Optional(ATTR_ADD_CHECKLIST_ITEM): vol.All(cv.ensure_list, [str]),
        vol.Optional(ATTR_REMOVE_CHECKLIST_ITEM): vol.All(cv.ensure_list, [str]),
        vol.Optional(ATTR_SCORE_CHECKLIST_ITEM): vol.All(cv.ensure_list, [str]),
        vol.Optional(ATTR_UNSCORE_CHECKLIST_ITEM): vol.All(cv.ensure_list, [str]),
        vol.Optional(ATTR_START_DATE): cv.date,
        vol.Optional(ATTR_INTERVAL): vol.All(int, vol.Range(0)),
        vol.Optional(ATTR_REPEAT): vol.All(cv.ensure_list, [vol.In(WEEK_DAYS)]),
        vol.Optional(ATTR_REPEAT_MONTHLY): vol.All(
            cv.string, vol.In({"day_of_month", "day_of_week"})
        ),
        vol.Optional(ATTR_STREAK): vol.All(int, vol.Range(0)),
    }
)

SERVICE_UPDATE_TASK_SCHEMA = BASE_TASK_SCHEMA.extend(
    {
        vol.Required(ATTR_TASK): cv.string,
        vol.Optional(ATTR_REMOVE_TAG): vol.All(cv.ensure_list, [str]),
    }
)

SERVICE_CREATE_TASK_SCHEMA = BASE_TASK_SCHEMA.extend(
    {
        vol.Required(ATTR_NAME): cv.string,
    }
)

SERVICE_DAILY_SCHEMA = {
    vol.Optional(ATTR_REMINDER): vol.All(cv.ensure_list, [cv.time]),
    vol.Optional(ATTR_REMOVE_REMINDER): vol.All(cv.ensure_list, [cv.time]),
}


SERVICE_GET_TASKS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector({"integration": DOMAIN}),
        vol.Optional(ATTR_TYPE): vol.All(
            cv.ensure_list, [vol.All(vol.Upper, vol.In({x.name for x in TaskType}))]
        ),
        vol.Optional(ATTR_PRIORITY): vol.All(
            cv.ensure_list, [vol.All(vol.Upper, vol.In({x.name for x in TaskPriority}))]
        ),
        vol.Optional(ATTR_TASK): vol.All(cv.ensure_list, [str]),
        vol.Optional(ATTR_TAG): vol.All(cv.ensure_list, [str]),
        vol.Optional(ATTR_KEYWORD): cv.string,
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
    SERVICE_UPDATE_REWARD: TaskType.REWARD,
    SERVICE_CREATE_REWARD: TaskType.REWARD,
    SERVICE_UPDATE_HABIT: TaskType.HABIT,
    SERVICE_CREATE_HABIT: TaskType.HABIT,
    SERVICE_UPDATE_TODO: TaskType.TODO,
    SERVICE_CREATE_TODO: TaskType.TODO,
    SERVICE_UPDATE_DAILY: TaskType.DAILY,
    SERVICE_CREATE_DAILY: TaskType.DAILY,
}


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

    async def cast_skill(call: ServiceCall) -> ServiceResponse:
        """Skill action."""
        entry = get_config_entry(hass, call.data[ATTR_CONFIG_ENTRY])
        coordinator = entry.runtime_data

        skill = SKILL_MAP[call.data[ATTR_SKILL]]
        cost = COST_MAP[call.data[ATTR_SKILL]]

        try:
            task_id = next(
                task.id
                for task in coordinator.data.tasks
                if call.data[ATTR_TASK] in (str(task.id), task.alias, task.text)
            )
        except StopIteration as e:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="task_not_found",
                translation_placeholders={"task": f"'{call.data[ATTR_TASK]}'"},
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
                translation_placeholders={"skill": call.data[ATTR_SKILL]},
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
            return asdict(response.data)

    async def manage_quests(call: ServiceCall) -> ServiceResponse:
        """Accept, reject, start, leave or cancel quests."""
        entry = get_config_entry(hass, call.data[ATTR_CONFIG_ENTRY])
        coordinator = entry.runtime_data

        FUNC_MAP = {
            SERVICE_ABORT_QUEST: coordinator.habitica.abort_quest,
            SERVICE_ACCEPT_QUEST: coordinator.habitica.accept_quest,
            SERVICE_CANCEL_QUEST: coordinator.habitica.cancel_quest,
            SERVICE_LEAVE_QUEST: coordinator.habitica.leave_quest,
            SERVICE_REJECT_QUEST: coordinator.habitica.reject_quest,
            SERVICE_START_QUEST: coordinator.habitica.start_quest,
        }

        func = FUNC_MAP[call.service]

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
            return asdict(response.data)

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

    async def score_task(call: ServiceCall) -> ServiceResponse:
        """Score a task action."""
        entry = get_config_entry(hass, call.data[ATTR_CONFIG_ENTRY])
        coordinator = entry.runtime_data

        direction = (
            Direction.DOWN if call.data.get(ATTR_DIRECTION) == "down" else Direction.UP
        )
        try:
            task_id, task_value = next(
                (task.id, task.value)
                for task in coordinator.data.tasks
                if call.data[ATTR_TASK] in (str(task.id), task.alias, task.text)
            )
        except StopIteration as e:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="task_not_found",
                translation_placeholders={"task": f"'{call.data[ATTR_TASK]}'"},
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
            return asdict(response.data)

    async def transformation(call: ServiceCall) -> ServiceResponse:
        """User a transformation item on a player character."""

        entry = get_config_entry(hass, call.data[ATTR_CONFIG_ENTRY])
        coordinator = entry.runtime_data

        item = ITEMID_MAP[call.data[ATTR_ITEM]]
        # check if target is self
        if call.data[ATTR_TARGET] in (
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
                    and call.data[ATTR_TARGET].lower()
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
                    translation_placeholders={"target": f"'{call.data[ATTR_TARGET]}'"},
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
                translation_placeholders={"item": call.data[ATTR_ITEM]},
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
            return asdict(response.data)

    async def get_tasks(call: ServiceCall) -> ServiceResponse:
        """Get tasks action."""

        entry = get_config_entry(hass, call.data[ATTR_CONFIG_ENTRY])
        coordinator = entry.runtime_data
        response: list[TaskData] = coordinator.data.tasks

        if types := {TaskType[x] for x in call.data.get(ATTR_TYPE, [])}:
            response = [task for task in response if task.Type in types]

        if priority := {TaskPriority[x] for x in call.data.get(ATTR_PRIORITY, [])}:
            response = [task for task in response if task.priority in priority]

        if tasks := call.data.get(ATTR_TASK):
            response = [
                task
                for task in response
                if str(task.id) in tasks or task.alias in tasks or task.text in tasks
            ]

        if tags := call.data.get(ATTR_TAG):
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
        if keyword := call.data.get(ATTR_KEYWORD):
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

    async def create_or_update_task(call: ServiceCall) -> ServiceResponse:  # noqa: C901
        """Create or update task action."""
        entry = get_config_entry(hass, call.data[ATTR_CONFIG_ENTRY])
        coordinator = entry.runtime_data
        await coordinator.async_refresh()
        is_update = call.service in (
            SERVICE_UPDATE_HABIT,
            SERVICE_UPDATE_REWARD,
            SERVICE_UPDATE_TODO,
            SERVICE_UPDATE_DAILY,
        )
        task_type = SERVICE_TASK_TYPE_MAP[call.service]
        current_task = None

        if is_update:
            try:
                current_task = next(
                    task
                    for task in coordinator.data.tasks
                    if call.data[ATTR_TASK] in (str(task.id), task.alias, task.text)
                    and task.Type is task_type
                )
            except StopIteration as e:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="task_not_found",
                    translation_placeholders={"task": f"'{call.data[ATTR_TASK]}'"},
                ) from e

        data = Task()

        if not is_update:
            data["type"] = task_type

        if (text := call.data.get(ATTR_RENAME)) or (text := call.data.get(ATTR_NAME)):
            data["text"] = text

        if (notes := call.data.get(ATTR_NOTES)) is not None:
            data["notes"] = notes

        tags = cast(list[str], call.data.get(ATTR_TAG))
        remove_tags = cast(list[str], call.data.get(ATTR_REMOVE_TAG))

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
                            user_tags.get(tag_name.lower())
                            or (await create_tag(tag_name))
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

        if (alias := call.data.get(ATTR_ALIAS)) is not None:
            data["alias"] = alias

        if (cost := call.data.get(ATTR_COST)) is not None:
            data["value"] = cost

        if priority := call.data.get(ATTR_PRIORITY):
            data["priority"] = TaskPriority[priority]

        if frequency := call.data.get(ATTR_FREQUENCY):
            data["frequency"] = frequency
        else:
            frequency = current_task.frequency if current_task else Frequency.WEEKLY

        if up_down := call.data.get(ATTR_UP_DOWN):
            data["up"] = "up" in up_down
            data["down"] = "down" in up_down

        if counter_up := call.data.get(ATTR_COUNTER_UP):
            data["counterUp"] = counter_up

        if counter_down := call.data.get(ATTR_COUNTER_DOWN):
            data["counterDown"] = counter_down

        if due_date := call.data.get(ATTR_DATE):
            data["date"] = datetime.combine(due_date, time())

        if call.data.get(ATTR_CLEAR_DATE):
            data["date"] = None

        checklist = current_task.checklist if current_task else []

        if add_checklist_item := call.data.get(ATTR_ADD_CHECKLIST_ITEM):
            checklist.extend(
                Checklist(completed=False, id=uuid4(), text=item)
                for item in add_checklist_item
                if not any(i.text == item for i in checklist)
            )
        if remove_checklist_item := call.data.get(ATTR_REMOVE_CHECKLIST_ITEM):
            checklist = [
                item for item in checklist if item.text not in remove_checklist_item
            ]

        if score_checklist_item := call.data.get(ATTR_SCORE_CHECKLIST_ITEM):
            for item in checklist:
                if item.text in score_checklist_item:
                    item.completed = True

        if unscore_checklist_item := call.data.get(ATTR_UNSCORE_CHECKLIST_ITEM):
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

        reminders = current_task.reminders if current_task else []

        if add_reminders := call.data.get(ATTR_REMINDER):
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
                        time=datetime.combine(date.today(), r, tzinfo=UTC),
                    )
                    for r in add_reminders
                    if r not in existing_reminder_times
                )

        if remove_reminder := call.data.get(ATTR_REMOVE_REMINDER):
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
                        lambda r: r.time.time().replace(second=0, microsecond=0)
                        not in remove_reminder,
                        reminders,
                    )
                )

        if clear_reminders := call.data.get(ATTR_CLEAR_REMINDER):
            reminders = []

        if add_reminders or remove_reminder or clear_reminders:
            data["reminders"] = reminders

        if start_date := call.data.get(ATTR_START_DATE):
            data["startDate"] = datetime.combine(start_date, time())
        else:
            start_date = (
                current_task.startDate
                if current_task and current_task.startDate
                else dt_util.start_of_local_day()
            )
        if repeat := call.data.get(ATTR_REPEAT):
            if frequency is Frequency.WEEKLY:
                data["repeat"] = Repeat(**{d: d in repeat for d in WEEK_DAYS})
            else:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="frequency_not_weekly",
                )
        if repeat_monthly := call.data.get(ATTR_REPEAT_MONTHLY):
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

        if interval := call.data.get(ATTR_INTERVAL):
            data["everyX"] = interval

        if streak := call.data.get(ATTR_STREAK):
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
            return response.data.to_dict(omit_none=True)

    for service in (
        SERVICE_UPDATE_DAILY,
        SERVICE_UPDATE_HABIT,
        SERVICE_UPDATE_REWARD,
        SERVICE_UPDATE_TODO,
    ):
        hass.services.async_register(
            DOMAIN,
            service,
            create_or_update_task,
            schema=SERVICE_UPDATE_TASK_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )
    for service in (
        SERVICE_CREATE_DAILY,
        SERVICE_CREATE_HABIT,
        SERVICE_CREATE_REWARD,
        SERVICE_CREATE_TODO,
    ):
        hass.services.async_register(
            DOMAIN,
            service,
            create_or_update_task,
            schema=SERVICE_CREATE_TASK_SCHEMA,
            supports_response=SupportsResponse.ONLY,
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
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_TASKS,
        get_tasks,
        schema=SERVICE_GET_TASKS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
