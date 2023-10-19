"""The TvOverlay integration."""
from tvoverlay import Notifications
from tvoverlay.exceptions import ConnectError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DATA_HASS_CONFIG, DOMAIN

PLATFORMS = [Platform.NOTIFY]

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the TvOverlay component."""

    hass.data[DATA_HASS_CONFIG] = config
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TvOverlay config entry."""

    notifier = Notifications(entry.data[CONF_HOST])

    try:
        await notifier.async_connect()
    except ConnectError as ex:
        raise ConfigEntryNotReady(
            f"Failed to connect to host: {entry.data[CONF_HOST]}"
        ) from ex

    hass.data.setdefault(DOMAIN, {})

    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            dict(entry.data),
            hass.data[DATA_HASS_CONFIG],
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload TvOverlay config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
