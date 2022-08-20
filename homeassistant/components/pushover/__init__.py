"""The pushover component."""
from __future__ import annotations

from pushover_complete import BadAPIRequestError, PushoverAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import discovery
from homeassistant.helpers.typing import ConfigType

from .const import CONF_USER_KEY, DATA_HASS_CONFIG, DOMAIN

PLATFORMS = [Platform.NOTIFY]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the pushover component."""

    hass.data[DATA_HASS_CONFIG] = config
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up pushover from a config entry."""

    pushover_api = PushoverAPI(entry.data[CONF_API_KEY])
    try:
        await hass.async_add_executor_job(
            pushover_api.validate, entry.data[CONF_USER_KEY]
        )

    except BadAPIRequestError as err:
        if "application token is invalid" in str(err):
            raise ConfigEntryAuthFailed(err) from err
        raise ConfigEntryNotReady(err) from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = pushover_api

    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            {
                CONF_NAME: entry.data[CONF_NAME],
                CONF_USER_KEY: entry.data[CONF_USER_KEY],
                "entry_id": entry.entry_id,
            },
            hass.data[DATA_HASS_CONFIG],
        )
    )

    return True
