"""The Bryant Evolution integration."""

from __future__ import annotations

import logging

from evolutionhttp import BryantEvolutionLocalClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_FILENAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from . import names
from .const import CONF_SYSTEM_ZONE, DOMAIN

PLATFORMS: list[Platform] = [Platform.CLIMATE]

type BryantEvolutionLocalClients = dict[tuple[int, int], BryantEvolutionLocalClient]
type BryantEvolutionConfigEntry = ConfigEntry[BryantEvolutionLocalClients]
_LOGGER = logging.getLogger(__name__)


async def _can_reach_device(client: BryantEvolutionLocalClient) -> bool:
    """Return whether we can reach the device at the given filename."""
    # Verify that we can read current temperature to check that the
    # (filename, system, zone) is valid.
    return await client.read_current_temperature() is not None


async def async_setup_entry(
    hass: HomeAssistant, entry: BryantEvolutionConfigEntry
) -> bool:
    """Set up Bryant Evolution from a config entry."""

    # Add a device for the SAM itself.
    sam_uid = names.sam_device_uid(entry)
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, sam_uid)},
        manufacturer="Bryant",
        name="System Access Module",
    )

    # Add a device for each system.
    for sys_id in (1, 2):
        if not any(sz[0] == sys_id for sz in entry.data[CONF_SYSTEM_ZONE]):
            _LOGGER.debug(
                "Skipping system %s because it is not configured for this integration: %s",
                sys_id,
                entry.data[CONF_SYSTEM_ZONE],
            )
            continue
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, names.system_device_uid(sam_uid, sys_id))},
            via_device=(DOMAIN, names.sam_device_uid(entry)),
            manufacturer="Bryant",
            name=f"System {sys_id}",
        )

    # Create a client for every zone.
    entry.runtime_data = {}
    for sz in entry.data[CONF_SYSTEM_ZONE]:
        try:
            client = await BryantEvolutionLocalClient.get_client(
                sz[0], sz[1], entry.data[CONF_FILENAME]
            )
            if not await _can_reach_device(client):
                raise ConfigEntryNotReady
            entry.runtime_data[tuple(sz)] = client
        except FileNotFoundError as f:
            raise ConfigEntryNotReady from f
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: BryantEvolutionConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
