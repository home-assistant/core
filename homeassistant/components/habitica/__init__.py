"""The habitica integration."""

from http import HTTPStatus
import logging
from typing import Any, cast

from aiohttp import ClientResponseError
from habitipy.aio import HabitipyAsync
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    APPLICATION_NAME,
    ATTR_NAME,
    CONF_API_KEY,
    CONF_NAME,
    CONF_URL,
    CONF_VERIFY_SSL,
    Platform,
    __version__,
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
    ATTR_ARGS,
    ATTR_CONFIG_ENTRY,
    ATTR_DATA,
    ATTR_KEYWORD,
    ATTR_PATH,
    ATTR_PRIORITY,
    ATTR_SKILL,
    ATTR_TAG,
    ATTR_TASK,
    ATTR_TYPE,
    CONF_API_USER,
    DEVELOPER_ID,
    DOMAIN,
    EVENT_API_CALL_SUCCESS,
    PRIORITIES,
    SERVICE_API_CALL,
    SERVICE_CAST_SKILL,
    SERVICE_GET_TASKS,
)
from .coordinator import HabiticaDataUpdateCoordinator
from .util import get_config_entry

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
SERVICE_GET_TASKS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector(),
        vol.Optional(ATTR_TYPE): vol.All(
            cv.ensure_list, [vol.In({"habit", "daily", "reward", "todo"})]
        ),
        vol.Optional(ATTR_PRIORITY): vol.All(
            cv.ensure_list, [vol.In(set(PRIORITIES.keys()))]
        ),
        vol.Optional(ATTR_TASK): vol.All(cv.ensure_list, [str]),
        vol.Optional(ATTR_TAG): vol.All(cv.ensure_list, [str]),
        vol.Optional(ATTR_KEYWORD): str,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Habitica service."""

    async def cast_skill(call: ServiceCall) -> ServiceResponse:
        """Skill action."""

        entry: HabiticaConfigEntry = get_config_entry(
            hass, call.data[ATTR_CONFIG_ENTRY]
        )
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

    async def get_tasks(call: ServiceCall) -> ServiceResponse:
        """Get tasks action."""

        entry: HabiticaConfigEntry = get_config_entry(
            hass, call.data[ATTR_CONFIG_ENTRY]
        )
        coordinator = entry.runtime_data
        response = coordinator.data.tasks

        if types := call.data.get(ATTR_TYPE):
            response = [task for task in response if task["type"] in types]

        if priority := call.data.get(ATTR_PRIORITY):
            priority = [PRIORITIES[k] for k in priority]
            response = [
                task
                for task in response
                if task.get("priority") is None or task.get("priority") in priority
            ]

        if tasks := call.data.get(ATTR_TASK):
            response = [
                task
                for task in response
                if task["id"] in tasks
                or task.get("alias") in tasks
                or task["text"] in tasks
            ]

        if tags := call.data.get(ATTR_TAG):
            tag_ids = {
                tag["id"]
                for tag in coordinator.data.user.get("tags", [])
                if tag["name"].lower()
                in (tag.lower() for tag in tags)  # Case-insensitive matching
            }

            response = [
                task
                for task in response
                if any(tag_id in task.get("tags", []) for tag_id in tag_ids)
            ]
        if keyword := call.data.get(ATTR_KEYWORD):
            keyword = keyword.lower()
            response = [
                task
                for task in response
                if keyword in task["text"].lower()
                or keyword in task["notes"].lower()
                or any(
                    keyword in item["text"].lower()
                    for item in task.get("checklist", [])
                )
            ]
        return cast(
            ServiceResponse,
            {
                "tasks": response,
            },
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
        SERVICE_GET_TASKS,
        get_tasks,
        schema=SERVICE_GET_TASKS_SCHEMA,
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

        def _make_headers(self) -> dict[str, str]:
            headers = super()._make_headers()
            headers.update(
                {"x-client": f"{DEVELOPER_ID} - {APPLICATION_NAME} {__version__}"}
            )
            return headers

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
