"""The DirecTV integration."""

from datetime import timedelta

from directv import DIRECTV, DIRECTVError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

PLATFORMS = [Platform.MEDIA_PLAYER, Platform.REMOTE]
SCAN_INTERVAL = timedelta(seconds=30)


type DirecTVConfigEntry = ConfigEntry[DIRECTV]


async def async_setup_entry(hass: HomeAssistant, entry: DirecTVConfigEntry) -> bool:
    """Set up DirecTV from a config entry."""
    dtv = DIRECTV(entry.data[CONF_HOST], session=async_get_clientsession(hass))

    try:
        await dtv.update()
    except DIRECTVError as err:
        raise ConfigEntryNotReady from err

    entry.runtime_data = dtv

    # Register the receiver device so client entities can link to it via_device_id.
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, dtv.device.info.receiver_id)},
        manufacturer=dtv.device.info.brand,
        name=next(
            (
                str.title(location.name)
                for location in dtv.device.locations
                if not location.client
            ),
            None,
        ),
        sw_version=dtv.device.info.version,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DirecTVConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
