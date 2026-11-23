"""The PoolSense integration."""

from poolsense import PoolSense

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN
from .coordinator import PoolSenseConfigEntry, PoolSenseDataUpdateCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: PoolSenseConfigEntry) -> None:
    """Set up PoolSense from a config entry."""

    poolsense = PoolSense(
        aiohttp_client.async_get_clientsession(hass),
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
        None,
    )
    auth_valid = await poolsense.test_poolsense_credentials()

    if not auth_valid:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        )

    coordinator = PoolSenseDataUpdateCoordinator(hass, entry, poolsense)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: PoolSenseConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
