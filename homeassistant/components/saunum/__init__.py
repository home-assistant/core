"""The Saunum Leil Sauna Control Unit integration."""

from __future__ import annotations

from pysaunum import SaunumClient, SaunumConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import LeilSaunaCoordinator
from .services import async_setup_services

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SENSOR,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type LeilSaunaConfigEntry = ConfigEntry[LeilSaunaCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Saunum component."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: LeilSaunaConfigEntry) -> bool:
    """Set up Saunum Leil Sauna from a config entry."""
    host = entry.data[CONF_HOST]

    try:
        client = await SaunumClient.create(host)
    except SaunumConnectionError as exc:
        raise ConfigEntryNotReady(f"Error connecting to {host}: {exc}") from exc

    entry.async_on_unload(client.async_close)

    coordinator = LeilSaunaCoordinator(hass, client, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LeilSaunaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
