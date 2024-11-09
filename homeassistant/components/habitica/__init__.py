"""The habitica integration."""

from http import HTTPStatus

from aiohttp import ClientResponseError
from habitipy.aio import HabitipyAsync

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
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import CONF_API_USER, DEVELOPER_ID, DOMAIN
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
