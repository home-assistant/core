"""The habitica integration."""

from http import HTTPStatus
import logging

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
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_ARGS,
    ATTR_DATA,
    ATTR_PATH,
    CONF_API_USER,
    DEVELOPER_ID,
    DOMAIN,
    EVENT_API_CALL_SUCCESS,
    SERVICE_API_CALL,
)
from .coordinator import HabiticaDataUpdateCoordinator
from .services import async_setup_services
from .types import HabiticaConfigEntry

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


PLATFORMS = [Platform.BUTTON, Platform.SENSOR, Platform.SWITCH, Platform.TODO]


SERVICE_API_CALL_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_NAME): str,
        vol.Required(ATTR_PATH): vol.All(cv.ensure_list, [str]),
        vol.Optional(ATTR_ARGS): dict,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Habitica service."""

    async_setup_services(hass)

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
