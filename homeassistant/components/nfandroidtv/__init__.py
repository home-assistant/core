"""The NFAndroidTV integration."""
from notifications_android_tv.notifications import ConnectError, Notifications

from homeassistant.components.notify import DOMAIN as NOTIFY
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import discovery

from .const import DOMAIN

PLATFORMS = [NOTIFY]


async def async_setup(hass: HomeAssistant, config):
    """Set up the NFAndroidTV component."""
    hass.data.setdefault(DOMAIN, {})
    # Iterate all entries for notify to only get nfandroidtv
    if NOTIFY in config:
        for entry in config[NOTIFY]:
            if entry[CONF_PLATFORM] == DOMAIN:
                hass.async_create_task(
                    hass.config_entries.flow.async_init(
                        DOMAIN, context={"source": SOURCE_IMPORT}, data=entry
                    )
                )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NFAndroidTV from a config entry."""
    host = entry.data[CONF_HOST]
    name = entry.data[CONF_NAME]

    try:
        await hass.async_add_executor_job(Notifications, host)
    except ConnectError as ex:
        raise ConfigEntryNotReady("Failed to connect") from ex

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        CONF_HOST: host,
        CONF_NAME: name,
    }

    hass.async_create_task(
        discovery.async_load_platform(
            hass, NOTIFY, DOMAIN, hass.data[DOMAIN][entry.entry_id], hass.data[DOMAIN]
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
