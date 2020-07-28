"""The syncthing integration."""
import asyncio
import logging

import aiosyncthing
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_TOKEN,
    CONF_URL,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_VERIFY_SSL,
    DOMAIN,
    EVENTS,
    RECONNECT_INTERVAL,
    SERVER_AVAILABLE,
    SERVER_UNAVAILABLE,
)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

PLATFORMS = ["sensor"]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the syncthing component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up syncthing from a config entry."""
    data = entry.data

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    name = data[CONF_NAME]

    client = aiosyncthing.Syncthing(
        data[CONF_TOKEN],
        url=data[CONF_URL],
        verify_ssl=data[CONF_VERIFY_SSL],
        loop=hass.loop,
    )

    listen_task = hass.loop.create_task(listen(hass, client, name))

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    hass.data[DOMAIN][name] = {
        "client": client,
        "listen_task": listen_task,
    }

    async def cancel_listen_task(_):
        listen_task.cancel()
        await hass.data[DOMAIN][name]["client"].close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cancel_listen_task)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        name = entry.data[CONF_NAME]
        hass.data[DOMAIN][name]["listen_task"].cancel()
        await hass.data[DOMAIN][name]["client"].close()
        hass.data[DOMAIN].pop(name)

    return unload_ok


async def listen(hass, client, name):
    """Listen to Syncthing events."""
    events = client.events
    server_was_unavailable = False
    while True:
        try:
            await client.system.ping()
            if server_was_unavailable:
                _LOGGER.info(f"The syncthing server {name} is back online.")
                async_dispatcher_send(hass, f"{SERVER_AVAILABLE}-{name}")
                server_was_unavailable = False

            async for event in events.listen():
                if events.last_seen_id == 0:
                    continue  # skipping historical events from the first batch
                if event["type"] not in EVENTS:
                    continue

                signal_name = EVENTS[event["type"]]
                folder = None
                if "folder" in event["data"]:
                    folder = event["data"]["folder"]
                else:  # A workaround, some events store folder id under `id` key
                    folder = event["data"]["id"]
                async_dispatcher_send(
                    hass, f"{signal_name}-{name}-{folder}", event,
                )
            return
        except aiosyncthing.exceptions.SyncthingError:
            _LOGGER.info(
                f"The syncthing event listener crashed. Probably, the server is not available. Sleeping {RECONNECT_INTERVAL.seconds} seconds and retrying..."
            )
            async_dispatcher_send(hass, f"{SERVER_UNAVAILABLE}-{name}")
            await asyncio.sleep(RECONNECT_INTERVAL.seconds)
            server_was_unavailable = True
            continue
