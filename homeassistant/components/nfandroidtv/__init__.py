"""The NFAndroidTV integration."""

from notifications_android_tv import ConnectError, Notifications

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.typing import ConfigType

from .const import DATA_HASS_CONFIG, DOMAIN

PLATFORMS = [Platform.NOTIFY]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type NFAndroidConfigEntry = ConfigEntry[Notifications]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the NFAndroidTV component."""

    hass.data[DATA_HASS_CONFIG] = config
    return True


async def async_setup_entry(hass: HomeAssistant, entry: NFAndroidConfigEntry) -> bool:
    """Set up NFAndroidTV from a config entry."""
    session = get_async_client(hass, verify_ssl=False)
    try:
        notifier = Notifications(entry.data[CONF_HOST], httpx_client=session)
        await notifier.async_connect()
    except ConnectError as ex:
        raise ConfigEntryNotReady(
            f"Failed to connect to host: {entry.data[CONF_HOST]}"
        ) from ex

    entry.runtime_data = notifier

    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            {CONF_NAME: entry.data[CONF_NAME], "entry_id": entry.entry_id},
            hass.data[DATA_HASS_CONFIG],
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
