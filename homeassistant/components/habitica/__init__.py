"""The habitica integration."""

from http import HTTPStatus
from typing import cast

from aiohttp import ClientResponseError
from habitipy.aio import HabitipyAsync
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    APPLICATION_NAME,
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
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import ConfigEntrySelector
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_CONFIG_ENTRY,
    ATTR_KEYWORD,
    ATTR_PRIORITY,
    ATTR_TAG,
    ATTR_TASK,
    ATTR_TYPE,
    CONF_API_USER,
    DEVELOPER_ID,
    DOMAIN,
    PRIORITIES,
    SERVICE_GET_TASKS,
)
from .coordinator import HabiticaDataUpdateCoordinator
from .services import async_setup_services
from .types import HabiticaConfigEntry

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CALENDAR,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TODO,
]

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

    async_setup_services(hass)

    async def get_tasks(call: ServiceCall) -> ServiceResponse:
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

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
