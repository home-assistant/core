"""Support for the LiteJet lighting system."""

import logging

import pylitejet

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, PLATFORMS

type LiteJetConfigEntry = ConfigEntry[pylitejet.LiteJet]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: LiteJetConfigEntry) -> None:
    """Set up LiteJet via a config entry."""
    port = entry.data[CONF_PORT]

    try:
        system = await pylitejet.open(port)
    except pylitejet.LiteJetError as exc:
        raise ConfigEntryNotReady from exc

    def handle_connected_changed(connected: bool, reason: str) -> None:
        if connected:
            _LOGGER.debug("Connected")
        else:
            _LOGGER.warning("Disconnected %s", reason)

    system.on_connected_changed(handle_connected_changed)

    async def handle_stop(event: Event) -> None:
        await system.close()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, handle_stop)
    )

    entry.runtime_data = system

    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_mcp")},
        name="LiteJet",
        manufacturer="Centralite",
        model=system.model_name,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: LiteJetConfigEntry) -> None:
    """Unload a LiteJet config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)

    await entry.runtime_data.close()
