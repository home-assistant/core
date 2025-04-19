"""The Rexense integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_HOST, CONF_PORT, DOMAIN
from .websocket_client import RexenseWebsocketClient

_LOGGER = logging.getLogger(__name__)

# Typed alias for ConfigEntry with runtime_data of type RexenseWebsocketClient
type RexenseConfigEntry = ConfigEntry[RexenseWebsocketClient]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RexenseConfigEntry,
) -> bool:
    """Set up Rexense from a config entry."""
    host: str = entry.data[CONF_HOST]
    port: int = entry.data.get(CONF_PORT, 80)
    model: str = entry.data.get("model", "Rexense Device")
    device_id: str = entry.unique_id or entry.data["device_id"]
    sw_build_id: str = entry.data.get("sw_build_id", "unknown")
    # e.g. [{"EP":1,"Attributes":["Current","Voltage","ActivePower","AprtPower","PowerFactor"],"Services":["OnOff"]}]
    feature_map: list[dict[str, str]] = entry.data.get("feature_map", [])

    ws_url = f"ws://{host}:{port}/rpc"
    client = RexenseWebsocketClient(
        hass, device_id, model, ws_url, sw_build_id, feature_map
    )
    try:
        await client.connect()
    except Exception as err:
        _LOGGER.error(
            "Failed to connect to Rexense device %s (%s): %s",
            device_id,
            host,
            err,
        )
        raise ConfigEntryNotReady from err

    entry.runtime_data = client

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client
    # Forward to sensor and switch platforms
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "switch"])
    _LOGGER.debug("Rexense integration setup complete for device %s", device_id)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: RexenseConfigEntry,
) -> bool:
    """Unload a Rexense config entry."""
    client: RexenseWebsocketClient = entry.runtime_data
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, ["sensor", "switch"]
    )
    if unload_ok:
        await client.disconnect()
    return unload_ok
