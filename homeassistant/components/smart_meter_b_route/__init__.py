"""The Smart Meter B Route integration."""

from momonga import MomongaError, MomongaKeyError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, CONF_ID, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import BRouteUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type BRouteConfigEntry = ConfigEntry[BRouteUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: BRouteConfigEntry) -> bool:
    """Set up Smart Meter B Route from a config entry."""

    device = entry.data[CONF_DEVICE]
    bid = entry.data[CONF_ID]
    password = entry.data[CONF_PASSWORD]
    hass.data.setdefault(DOMAIN, {})
    coordinator = BRouteUpdateCoordinator(hass, device, bid, password)
    try:
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = coordinator
    except MomongaError | MomongaKeyError as ex:
        raise ConfigEntryNotReady from ex
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BRouteConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
