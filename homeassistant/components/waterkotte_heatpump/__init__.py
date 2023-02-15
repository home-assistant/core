"""The Waterkotte Heatpump integration."""
from __future__ import annotations

from pywaterkotte import AuthenticationException, ConnectionException, Ecotouch

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, DOMAIN
from .coordinator import EcotouchCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Waterkotte Heatpump from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    try:

        def create_heatpump_instance(username: str, password: str) -> Ecotouch:
            """Create and initialize a heatpump instance."""
            heatpump = Ecotouch(entry.data.get(CONF_HOST))
            heatpump.login(username, password)
            return heatpump

        heatpump = await hass.async_add_executor_job(
            create_heatpump_instance,
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
        )
    except (ConnectionException, AuthenticationException) as ex:
        raise ConfigEntryNotReady(
            f"Timeout while connecting to {entry.data.get(CONF_HOST)}"
        ) from ex

    coordinator = EcotouchCoordinator(heatpump, hass)

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
