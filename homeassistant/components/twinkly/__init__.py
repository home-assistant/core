"""The twinkly component."""

import logging

from aiohttp import ClientError
from ttls.client import Twinkly

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import TwinklyConfigEntry, TwinklyCoordinator

PLATFORMS = [Platform.LIGHT, Platform.SELECT]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: TwinklyConfigEntry) -> bool:
    """Set up entries from config flow."""
    # We setup the client here so if at some point we add any other entity for this device,
    # we will be able to properly share the connection.
    host = entry.data[CONF_HOST]

    client = Twinkly(host, async_get_clientsession(hass))

    coordinator = TwinklyCoordinator(hass, entry, client)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: TwinklyConfigEntry) -> bool:
    """Remove a twinkly entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: TwinklyConfigEntry) -> bool:
    """Migrate old entry."""
    if entry.minor_version == 1:
        client = Twinkly(entry.data[CONF_HOST], async_get_clientsession(hass))
        try:
            device_info = await client.get_details()
        except (TimeoutError, ClientError) as exception:
            _LOGGER.error("Error while migrating: %s", exception)
            return False
        identifier = entry.unique_id
        assert identifier is not None
        entity_registry = er.async_get(hass)
        entity_id = entity_registry.async_get_entity_id("light", DOMAIN, identifier)
        if entity_id:
            entity_entry = entity_registry.async_get(entity_id)
            assert entity_entry is not None
            entity_registry.async_update_entity(
                entity_entry.entity_id, new_unique_id=device_info["mac"]
            )
        device_registry = dr.async_get(hass)
        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN, identifier)}
        )
        if device_entry:
            device_registry.async_update_device(
                device_entry.id, new_identifiers={(DOMAIN, device_info["mac"])}
            )
        hass.config_entries.async_update_entry(
            entry,
            unique_id=device_info["mac"],
            minor_version=2,
        )

    return True
