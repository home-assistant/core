"""The Marstek integration."""

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import MarstekConfigEntry, MarstekDataUpdateCoordinator
from .helpers import async_get_udp_client

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: MarstekConfigEntry) -> None:
    """Set up Marstek from a config entry."""
    try:
        udp_client = await async_get_udp_client(hass)
    except (TimeoutError, OSError, TypeError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="udp_client_failed",
        ) from err
    coordinator = MarstekDataUpdateCoordinator(hass, entry, udp_client)
    entry.runtime_data = coordinator
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: MarstekConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
