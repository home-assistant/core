"""Support for Ezviz camera."""
from __future__ import annotations

import logging

from pyezviz.client import EzvizClient
from pyezviz.exceptions import (
    EzvizAuthTokenExpired,
    EzvizAuthVerificationCode,
    HTTPError,
    InvalidURL,
    PyEzvizError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_TIMEOUT,
    CONF_TYPE,
    CONF_URL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import (
    ATTR_TYPE_CAMERA,
    ATTR_TYPE_CLOUD,
    CONF_FFMPEG_ARGUMENTS,
    CONF_RFSESSION_ID,
    CONF_SESSION_ID,
    DATA_COORDINATOR,
    DEFAULT_FFMPEG_ARGUMENTS,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from .coordinator import EzvizDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS_BY_TYPE: dict[str, list] = {
    ATTR_TYPE_CAMERA: [],
    ATTR_TYPE_CLOUD: [
        Platform.BINARY_SENSOR,
        Platform.CAMERA,
        Platform.SENSOR,
        Platform.SWITCH,
    ],
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EZVIZ from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    sensor_type: str = entry.data[CONF_TYPE]
    ezviz_client = None

    if not entry.options:
        options = {
            CONF_FFMPEG_ARGUMENTS: DEFAULT_FFMPEG_ARGUMENTS,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
        }

        hass.config_entries.async_update_entry(entry, options=options)

    if PLATFORMS_BY_TYPE[sensor_type]:

        # Get user account token if not present.
        if not entry.data.get(CONF_SESSION_ID):

            try:
                ezviz_client = await _get_ezviz_client_instance(hass, entry)

            except (InvalidURL, HTTPError, PyEzvizError) as error:
                _LOGGER.error("Unable to connect to Ezviz service: %s", str(error))
                raise ConfigEntryNotReady from error

        if not ezviz_client:
            # No Ezviz login session, call api login().

            ezviz_client = EzvizClient(
                token={
                    CONF_SESSION_ID: entry.data.get(CONF_SESSION_ID),
                    CONF_RFSESSION_ID: entry.data.get(CONF_RFSESSION_ID),
                    "api_url": entry.data.get(CONF_URL),
                },
                timeout=entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
            )

            try:
                await hass.async_add_executor_job(ezviz_client.login)

            except (EzvizAuthTokenExpired, EzvizAuthVerificationCode) as error:
                raise ConfigEntryAuthFailed from error

            except (InvalidURL, HTTPError, PyEzvizError) as error:
                _LOGGER.error("Unable to connect to Ezviz service: %s", str(error))
                raise ConfigEntryNotReady from error

        coordinator = EzvizDataUpdateCoordinator(
            hass, api=ezviz_client, api_timeout=entry.options[CONF_TIMEOUT]
        )

        hass.data[DOMAIN][entry.entry_id] = {DATA_COORDINATOR: coordinator}

        await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    if sensor_type == ATTR_TYPE_CAMERA:
        if hass.data.get(DOMAIN):
            for item in hass.config_entries.async_entries(domain=DOMAIN):
                if item.data.get(CONF_TYPE) == ATTR_TYPE_CLOUD:
                    _LOGGER.info("Reload Ezviz main account with camera entry")
                    await hass.config_entries.async_reload(item.entry_id)
                    return True

    hass.config_entries.async_setup_platforms(entry, PLATFORMS_BY_TYPE[sensor_type])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    sensor_type = entry.data[CONF_TYPE]

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS_BY_TYPE[sensor_type]
    )
    if sensor_type == ATTR_TYPE_CLOUD and unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _get_ezviz_client_instance(
    hass: HomeAssistant, entry: ConfigEntry
) -> EzvizClient:
    """Initialize a new instance of EzvizClientApi with username and password."""
    ezviz_client = EzvizClient(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data[CONF_URL],
        entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
    )

    _token = await hass.async_add_executor_job(ezviz_client.login)

    if _token:
        _LOGGER.info("Updating Ezviz Login token")

        hass.config_entries.async_update_entry(
            entry,
            data={
                CONF_URL: entry.data[CONF_URL],
                CONF_SESSION_ID: _token[CONF_SESSION_ID],
                CONF_RFSESSION_ID: _token[CONF_RFSESSION_ID],
                CONF_TYPE: ATTR_TYPE_CLOUD,
            },
        )

    return ezviz_client
