"""The habitica integration."""

from datetime import datetime, time
from http import HTTPStatus
import logging
from typing import Any
import uuid

from aiohttp import ClientResponseError
from habitipy.aio import HabitipyAsync
import voluptuous as vol

from homeassistant.components.todo import ATTR_DESCRIPTION, ATTR_RENAME
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DATE,
    ATTR_NAME,
    CONF_API_KEY,
    CONF_NAME,
    CONF_URL,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import (
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import ConfigEntrySelector
from homeassistant.helpers.typing import ConfigType

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
    ATTR_FREQUENCY,
    ATTR_PATH,
    ATTR_PRIORITY,
    ATTR_REMINDER,
    ATTR_REMOVE_CHECKLIST_ITEM,
    ATTR_REMOVE_REMINDER,
    ATTR_REMOVE_TAG,
    ATTR_SCORE_CHECKLIST_ITEM,
    ATTR_SKILL,
    ATTR_TAG,
    ATTR_TASK,
    ATTR_UNSCORE_CHECKLIST_ITEM,
    ATTR_UP_DOWN,
    CONF_API_USER,
    DOMAIN,
    EVENT_API_CALL_SUCCESS,
    PRIORITIES,
    SERVICE_API_CALL,
    SERVICE_CAST_SKILL,
    SERVICE_UPDATE_DAILY,
    SERVICE_UPDATE_HABIT,
    SERVICE_UPDATE_REWARD,
    SERVICE_UPDATE_TODO,
)
from .coordinator import HabiticaDataUpdateCoordinator
from .util import get_config_entry, lookup_task

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type HabiticaConfigEntry = ConfigEntry[HabiticaDataUpdateCoordinator]


PLATFORMS = [Platform.BUTTON, Platform.SENSOR, Platform.SWITCH, Platform.TODO]


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
        vol.Optional(ATTR_REMOVE_REMINDER): vol.All(cv.ensure_list, [cv.datetime]),
        vol.Optional(ATTR_CLEAR_REMINDER): cv.boolean,
        vol.Optional(ATTR_COST): vol.All(int, float),
        vol.Optional(ATTR_ADD_CHECKLIST_ITEM): vol.All(cv.ensure_list, [str]),
        vol.Optional(ATTR_REMOVE_CHECKLIST_ITEM): vol.All(cv.ensure_list, [str]),
        vol.Optional(ATTR_SCORE_CHECKLIST_ITEM): vol.All(cv.ensure_list, [str]),
        vol.Optional(ATTR_UNSCORE_CHECKLIST_ITEM): vol.All(cv.ensure_list, [str]),
        vol.Optional(ATTR_UP_DOWN): vol.All(
            cv.ensure_list, [vol.In({"positive", "negative"})]
        ),
        vol.Optional(ATTR_FREQUENCY): vol.All(
            cv.string, vol.In({"daily", "weekly", "monthly", "yearly"})
        ),
        vol.Optional(ATTR_COUNTER_UP): int,
        vol.Optional(ATTR_COUNTER_DOWN): int,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:  # noqa: C901
    """Set up the Habitica service."""

    async def cast_skill(call: ServiceCall) -> ServiceResponse:
        """Skill action."""
        entry: HabiticaConfigEntry | None
        if not (
            entry := hass.config_entries.async_get_entry(call.data[ATTR_CONFIG_ENTRY])
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entry_not_found",
            )
        coordinator = entry.runtime_data
        skill = {
            "pickpocket": {"spellId": "pickPocket", "cost": "10 MP"},
            "backstab": {"spellId": "backStab", "cost": "15 MP"},
            "smash": {"spellId": "smash", "cost": "10 MP"},
            "fireball": {"spellId": "fireball", "cost": "10 MP"},
        }
        task_id = lookup_task(
            coordinator.data.tasks, call.data[ATTR_TASK], call.service
        )["id"]
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

        if reminder := call.data.get(ATTR_REMINDER):
            existing_reminder_times = {
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

        if call.data.get(ATTR_CLEAR_REMINDER):
            data.update({"reminders": []})

        if date := call.data.get(ATTR_DATE):
            data.update({"date": (datetime.combine(date, time()).isoformat())})

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
        if up_down := call.data.get(ATTR_UP_DOWN):
            data.update(
                {
                    "up": "positive" in up_down,
                    "down": "negative" in up_down,
                }
            )

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

    hass.services.async_register(
        DOMAIN,
        SERVICE_CAST_SKILL,
        cast_skill,
        schema=SERVICE_CAST_SKILL_SCHEMA,
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

    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: HabiticaConfigEntry
) -> bool:
    """Set up habitica from a config entry."""

    class HAHabitipyAsync(HabitipyAsync):
        """Closure API class to hold session."""

        def __call__(self, **kwargs):
            return super().__call__(websession, **kwargs)

    async def handle_api_call(call: ServiceCall) -> None:
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

    websession = async_get_clientsession(
        hass, verify_ssl=config_entry.data.get(CONF_VERIFY_SSL, True)
    )

    api = await hass.async_add_executor_job(
        HAHabitipyAsync,
        {
            "url": config_entry.data[CONF_URL],
            "login": config_entry.data[CONF_API_USER],
            "password": config_entry.data[CONF_API_KEY],
        },
    )
    try:
        user = await api.user.get(userFields="profile")
    except ClientResponseError as e:
        if e.status == HTTPStatus.TOO_MANY_REQUESTS:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="setup_rate_limit_exception",
            ) from e
        raise ConfigEntryNotReady(e) from e

    if not config_entry.data.get(CONF_NAME):
        name = user["profile"]["name"]
        hass.config_entries.async_update_entry(
            config_entry,
            data={**config_entry.data, CONF_NAME: name},
        )

    coordinator = HabiticaDataUpdateCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    config_entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    if not hass.services.has_service(DOMAIN, SERVICE_API_CALL):
        hass.services.async_register(
            DOMAIN, SERVICE_API_CALL, handle_api_call, schema=SERVICE_API_CALL_SCHEMA
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if len(hass.config_entries.async_entries(DOMAIN)) == 1:
        hass.services.async_remove(DOMAIN, SERVICE_API_CALL)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
