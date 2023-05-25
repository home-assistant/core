"""Support for Hydrawise cloud."""

from datetime import timedelta

from hydrawiser.core import Hydrawiser
from requests.exceptions import ConnectTimeout, HTTPError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_API_KEY,
    CONF_SCAN_INTERVAL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, LOGGER, SCAN_INTERVAL
from .coordinator import HydrawiseDataUpdateCoordinator

# Deprecated since Home Assistant 2023.7.0
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_ACCESS_TOKEN): cv.string,
                vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.SWITCH]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Hunter Hydrawise component."""
    if not hass.config_entries.async_entries(DOMAIN) and DOMAIN not in hass.data:
        # No config entry exists and configuration.yaml config exists; trigger the import flow.
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={
                    CONF_API_KEY: config[DOMAIN][CONF_ACCESS_TOKEN],
                    CONF_SCAN_INTERVAL: config[DOMAIN][CONF_SCAN_INTERVAL].seconds,
                },
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Hydrawise from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    access_token = config_entry.data[CONF_API_KEY]
    scan_interval = config_entry.data[CONF_SCAN_INTERVAL]
    try:
        hydrawise = await hass.async_add_executor_job(Hydrawiser, access_token)
        hass.data[DOMAIN][config_entry.entry_id] = HydrawiseDataUpdateCoordinator(
            hass, hydrawise, timedelta(seconds=scan_interval)
        )
    except (ConnectTimeout, HTTPError) as ex:
        LOGGER.error("Unable to connect to Hydrawise cloud service: %s", str(ex))
        raise ConfigEntryNotReady(
            f"Unable to connect to Hydrawise cloud service: {ex}"
        ) from ex

    if not hydrawise.controller_info or not hydrawise.controller_status:
        raise ConfigEntryNotReady("Hydrawise data not loaded")

    # NOTE: We don't need to call async_config_entry_first_refresh() because
    # data is fetched when the Hydrawiser object is instantiated.
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
