"""The Rexense integration using external rexense-wsclient library."""

from __future__ import annotations

from functools import partial
import logging

from aiorexense import RexenseWebsocketClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.dispatcher import dispatcher_send

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type RexenseConfigEntry = ConfigEntry[RexenseWebsocketClient]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RexenseConfigEntry,
) -> bool:
    """Set up the Rexense integration after the config entry is created."""
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, 80)
    model = entry.data.get(CONF_MODEL, "")
    device_id = entry.unique_id or entry.data["device_id"]
    sw_build_id = entry.data.get("sw_build_id", "unknown")
    feature_map = entry.data.get("feature_map", [])

    ws_url = f"ws://{host}:{port}/rpc"
    session = aiohttp_client.async_get_clientsession(hass)

    # Create the client and configure the Home Assistant dispatcher callback.
    client = RexenseWebsocketClient(
        device_id=device_id,
        model=model,
        url=ws_url,
        sw_build_id=sw_build_id,
        feature_map=feature_map,
        session=session,
    )

    client.on_update = partial(
        dispatcher_send, hass, f"{DOMAIN}_{client.device_id}_update"
    )
    client.signal_update = f"{DOMAIN}_{device_id}_update"

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
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    _LOGGER.debug("Rexense integration setup complete for device %s", device_id)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: RexenseConfigEntry,
) -> bool:
    """Unload the Rexense integration and disconnect the client."""
    client = entry.runtime_data
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, ["sensor"]
    )
    if unload_ok:
        await client.disconnect()
    return unload_ok
