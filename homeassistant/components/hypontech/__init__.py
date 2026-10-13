"""The Hypontech Cloud integration."""

from hyponcloud import AuthenticationError, HyponCloud, RequestError

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_OEM, DEFAULT_OEM
from .coordinator import HypontechConfigEntry, HypontechDataCoordinator

_PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: HypontechConfigEntry) -> None:
    """Set up Hypontech Cloud from a config entry."""
    session = async_get_clientsession(hass)
    hypontech_cloud = HyponCloud(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        session,
        oem=int(entry.data.get(CONF_OEM, DEFAULT_OEM)),
    )
    try:
        await hypontech_cloud.connect()
    except AuthenticationError as ex:
        raise ConfigEntryAuthFailed("Authentication failed for Hypontech Cloud") from ex
    except (RequestError, TimeoutError, ConnectionError) as ex:
        raise ConfigEntryNotReady("Cannot connect to Hypontech Cloud") from ex

    assert entry.unique_id
    coordinator = HypontechDataCoordinator(
        hass, entry, hypontech_cloud, entry.unique_id
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: HypontechConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, _PLATFORMS)
