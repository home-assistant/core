"""Support for LaMetric time."""
from demetriek import LaMetricConnectionError, LaMetricDevice
import voluptuous as vol

from homeassistant.components.repairs import IssueSeverity, async_create_issue
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_HOST,
    CONF_NAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Required(CONF_CLIENT_ID): cv.string,
                    vol.Required(CONF_CLIENT_SECRET): cv.string,
                }
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the LaMetric integration."""
    hass.data[DOMAIN] = {"hass_config": config}
    if DOMAIN in config:
        async_create_issue(
            hass,
            DOMAIN,
            "manual_migration",
            breaks_in_ha_version="2022.9.0",
            is_fixable=False,
            severity=IssueSeverity.ERROR,
            translation_key="manual_migration",
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LaMetric from a config entry."""
    lametric = LaMetricDevice(
        host=entry.data[CONF_HOST],
        api_key=entry.data[CONF_API_KEY],
        session=async_get_clientsession(hass),
    )

    try:
        device = await lametric.device()
    except LaMetricConnectionError as ex:
        raise ConfigEntryNotReady("Cannot connect to LaMetric device") from ex

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = lametric

    # Set up notify platform, no entry support for notify component yet,
    # have to use discovery to load platform.
    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            {CONF_NAME: device.name, "entry_id": entry.entry_id},
            hass.data[DOMAIN]["hass_config"],
        )
    )
    return True
