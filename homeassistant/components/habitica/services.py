"""Actions for the Habitica integration."""

from __future__ import annotations

from http import HTTPStatus
import logging
from typing import Any

from aiohttp import ClientResponseError
import voluptuous as vol

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
    ATTR_ARGS,
    ATTR_CONFIG_ENTRY,
    ATTR_DATA,
    ATTR_DIRECTION,
    ATTR_ITEM,
    ATTR_PATH,
    ATTR_SKILL,
    ATTR_TARGET,
    ATTR_TASK,
    DOMAIN,
    EVENT_API_CALL_SUCCESS,
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
)
from .types import HabiticaConfigEntry

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
