"""The Bbox integration."""

from aiohttp import CookieJar
from bbox_api import BboxClient

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import PLATFORMS
from .coordinator import BboxConfigEntry, BboxCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: BboxConfigEntry) -> None:
    """Set up a Bbox from a config entry."""
    password = entry.data[CONF_PASSWORD]
    if not password:
        # YAML-imported entries predate the password requirement: ask for
        # it through the reauth flow instead of failing the setup.
        raise ConfigEntryAuthFailed("The Bbox admin password is required")
    verify_ssl = entry.data[CONF_VERIFY_SSL]
    # A dedicated session with an unsafe cookie jar: the session cookie
    # must be kept when the box is reached by IP instead of a hostname.
    session = async_create_clientsession(
        hass, verify_ssl=verify_ssl, cookie_jar=CookieJar(unsafe=True)
    )
    client = BboxClient(
        password,
        entry.data[CONF_HOST],
        use_tls=True,
        verify_ssl=verify_ssl,
        session=session,
    )
    coordinator = BboxCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    # Detach the client on unload; the HA-managed session itself is
    # closed by the framework at shutdown.
    entry.async_on_unload(client.close)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: BboxConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
