"""Actions for the Habitica integration."""

from __future__ import annotations

from dataclasses import asdict
import logging
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from aiohttp import ClientError
from habiticalib import (
    Direction,
    Frequency,
    HabiticaException,
    NotAuthorizedError,
    NotFoundError,
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
from homeassistant.const import ATTR_NAME, CONF_NAME
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
    ATTR_ALIAS,
    ATTR_ARGS,
    ATTR_CONFIG_ENTRY,
    ATTR_COST,
    ATTR_COUNTER_DOWN,
    ATTR_COUNTER_UP,
    ATTR_DATA,
    ATTR_DIRECTION,
    ATTR_FREQUENCY,
    ATTR_ITEM,
    ATTR_KEYWORD,
    ATTR_NOTES,
    ATTR_PATH,
    ATTR_PRIORITY,
    ATTR_REMOVE_TAG,
    ATTR_SKILL,
    ATTR_TAG,
    ATTR_TARGET,
    ATTR_TASK,
    ATTR_TYPE,
    ATTR_UP_DOWN,
    DOMAIN,
    EVENT_API_CALL_SUCCESS,
    SERVICE_ABORT_QUEST,
    SERVICE_ACCEPT_QUEST,
    SERVICE_API_CALL,
    SERVICE_CANCEL_QUEST,
    SERVICE_CAST_SKILL,
    SERVICE_CREATE_HABIT,
    SERVICE_CREATE_REWARD,
    SERVICE_GET_TASKS,
    SERVICE_LEAVE_QUEST,
    SERVICE_REJECT_QUEST,
    SERVICE_SCORE_HABIT,
    SERVICE_SCORE_REWARD,
    SERVICE_START_QUEST,
    SERVICE_TRANSFORMATION,
    SERVICE_UPDATE_HABIT,
    SERVICE_UPDATE_REWARD,
)
from .coordinator import HabiticaConfigEntry

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
        entries: list[HabiticaConfigEntry] = hass.config_entries.async_entries(DOMAIN)

        api = None
        for entry in entries:
            if entry.data[CONF_NAME] == name:
                api = await entry.runtime_data.habitica.habitipy()
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
        is_update = call.service in (SERVICE_UPDATE_REWARD, SERVICE_UPDATE_HABIT)
        current_task = None

        if is_update:
            try:
                current_task = next(
                    task
                    for task in coordinator.data.tasks
                    if call.data[ATTR_TASK] in (str(task.id), task.alias, task.text)
                    and task.Type is SERVICE_TASK_TYPE_MAP[call.service]
                )
            except StopIteration as e:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="task_not_found",
                    translation_placeholders={"task": f"'{call.data[ATTR_TASK]}'"},
                ) from e

        data = Task()

        if not is_update:
            data["type"] = SERVICE_TASK_TYPE_MAP[call.service]

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

        if up_down := call.data.get(ATTR_UP_DOWN):
            data["up"] = "up" in up_down
            data["down"] = "down" in up_down

        if counter_up := call.data.get(ATTR_COUNTER_UP):
            data["counterUp"] = counter_up

        if counter_down := call.data.get(ATTR_COUNTER_DOWN):
            data["counterDown"] = counter_down

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

    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_REWARD,
        create_or_update_task,
        schema=SERVICE_UPDATE_TASK_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_HABIT,
        create_or_update_task,
        schema=SERVICE_UPDATE_TASK_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_REWARD,
        create_or_update_task,
        schema=SERVICE_CREATE_TASK_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_HABIT,
        create_or_update_task,
        schema=SERVICE_CREATE_TASK_SCHEMA,
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
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_TASKS,
        get_tasks,
        schema=SERVICE_GET_TASKS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
