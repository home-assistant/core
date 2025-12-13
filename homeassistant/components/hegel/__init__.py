"""The Hegel integration."""

from __future__ import annotations

import logging

from hegel_ip_client import HegelClient
from hegel_ip_client.exceptions import HegelConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]
_LOGGER = logging.getLogger(__name__)

type HegelConfigEntry = ConfigEntry[HegelClient]

# Service schemas
SERVICE_SEND_COMMAND = "send_command"

SEND_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_ids,
        vol.Required("command"): cv.string,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: HegelConfigEntry) -> bool:
    """Set up the Hegel integration."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    # Create and test client connection
    client = HegelClient(host, port)

    try:
        # Test connection before proceeding with setup
        await client.start()
        await client.ensure_connected(timeout=10.0)
        _LOGGER.debug("Successfully connected to Hegel at %s:%s", host, port)
    except (HegelConnectionError, TimeoutError, OSError) as err:
        _LOGGER.error("Failed to connect to Hegel at %s:%s: %s", host, port, err)
        await client.stop()  # Clean up
        raise ConfigEntryNotReady(
            f"Unable to connect to Hegel amplifier at {host}:{port}"
        ) from err

    # Store client in runtime_data
    entry.runtime_data = client

    async def _async_close_client(event):
        await client.stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_close_client)
    )

    # Forward setup to supported platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    await _async_register_services(hass)

    _LOGGER.debug("Hegel entry %s setup completed", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HegelConfigEntry) -> bool:
    """Unload a Hegel config entry and stop active client connection."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and entry.runtime_data:
        client = entry.runtime_data
        try:
            _LOGGER.debug("Stopping Hegel client for %s", entry.title)
            await client.stop()
        except (HegelConnectionError, OSError) as err:
            _LOGGER.warning("Error while stopping Hegel client: %s", err)

    return unload_ok


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register integration services."""

    # Only register services once
    if hass.services.has_service(DOMAIN, SERVICE_SEND_COMMAND):
        return

    async def async_send_command(call: ServiceCall) -> None:
        """Handle send_command service call."""
        entity_ids = call.data["entity_id"]
        command = call.data["command"]

        entity_registry = er.async_get(hass)

        for entity_id in entity_ids:
            entity = entity_registry.async_get(entity_id)
            if entity and entity.platform == DOMAIN:
                # Find the config entry for this entity
                for entry in hass.config_entries.async_entries(DOMAIN):
                    if hasattr(entry, "runtime_data") and entry.runtime_data:
                        client = entry.runtime_data
                        try:
                            await client.send(command, expect_reply=False)
                            _LOGGER.debug("Sent command '%s' to %s", command, entity_id)
                        except (HegelConnectionError, TimeoutError, OSError) as err:
                            _LOGGER.error(
                                "Failed to send command '%s' to %s: %s",
                                command,
                                entity_id,
                                err,
                            )

    # Register the service
    hass.services.async_register(
        DOMAIN, SERVICE_SEND_COMMAND, async_send_command, schema=SEND_COMMAND_SCHEMA
    )
