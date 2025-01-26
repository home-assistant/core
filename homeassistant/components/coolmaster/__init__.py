"""The Coolmaster integration."""

from pycoolmasternet_async import CoolMasterNet

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_SWING_SUPPORT
from .coordinator import CoolmasterConfigEntry, CoolmasterDataUpdateCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.CLIMATE, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: CoolmasterConfigEntry) -> bool:
    """Set up Coolmaster from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    if not entry.data.get(CONF_SWING_SUPPORT):
        coolmaster = CoolMasterNet(
            host,
            port,
        )
    else:
        # Swing support adds an additional request per unit. The requests are
        # done in parallel, which can cause delays on the server. Therefore,
        # we increase the request timeout to 5 seconds instead of 1.
        coolmaster = CoolMasterNet(
            host,
            port,
            read_timeout=5,
            swing_support=True,
        )
    try:
        info = await coolmaster.info()
        if not info:
            raise ConfigEntryNotReady
    except OSError as error:
        raise ConfigEntryNotReady from error
    coordinator = CoolmasterDataUpdateCoordinator(hass, entry, coolmaster, info)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CoolmasterConfigEntry) -> bool:
    """Unload a Coolmaster config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
