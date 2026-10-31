"""The FENIX Control integration."""

from pyfenixcontrol import FenixControlClient, PasswordAuth

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .coordinator import FenixControlConfigEntry, FenixControlCoordinator

_PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup_entry(
    hass: HomeAssistant, entry: FenixControlConfigEntry
) -> None:
    """Set up FENIX Control from a config entry."""
    # The login keeps identity-server cookies, so it needs its own cookie jar
    auth = PasswordAuth(
        async_create_clientsession(hass),
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
    )
    coordinator = FenixControlCoordinator(hass, entry, FenixControlClient(auth))
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: FenixControlConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, _PLATFORMS)
