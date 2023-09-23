"""Support for Hydrawise cloud."""


from pydrawise.legacy import LegacyHydrawise
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
    if DOMAIN not in config:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_API_KEY: config[DOMAIN][CONF_ACCESS_TOKEN]},
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Hydrawise from a config entry."""
    access_token = config_entry.data[CONF_API_KEY]
    try:
        hydrawise = await hass.async_add_executor_job(LegacyHydrawise, access_token)
    except (ConnectTimeout, HTTPError) as ex:
        LOGGER.error("Unable to connect to Hydrawise cloud service: %s", str(ex))
        raise ConfigEntryNotReady(
            f"Unable to connect to Hydrawise cloud service: {ex}"
        ) from ex

    hass.data.setdefault(DOMAIN, {})[
        config_entry.entry_id
    ] = HydrawiseDataUpdateCoordinator(hass, hydrawise, SCAN_INTERVAL)
    if not hydrawise.controller_info or not hydrawise.controller_status:
        raise ConfigEntryNotReady("Hydrawise data not loaded")

    # NOTE: We don't need to call async_config_entry_first_refresh() because
    # data is fetched when the Hydrawiser object is instantiated.
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
