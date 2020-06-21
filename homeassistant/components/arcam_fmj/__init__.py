"""Arcam component."""
import asyncio
import logging

from arcam.fmj import ConnectionFailed
from arcam.fmj.client import Client
import async_timeout

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    DOMAIN_DATA_ENTRIES,
    DOMAIN_DATA_TASKS,
    SIGNAL_CLIENT_DATA,
    SIGNAL_CLIENT_STARTED,
    SIGNAL_CLIENT_STOPPED,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.deprecated(DOMAIN, invalidation_version="0.115")


async def _await_cancel(task):
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Set up the component."""
    hass.data[DOMAIN_DATA_ENTRIES] = {}
    hass.data[DOMAIN_DATA_TASKS] = {}

    async def _stop(_):
        asyncio.gather(
            *[_await_cancel(task) for task in hass.data[DOMAIN_DATA_TASKS].values()]
        )

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop)

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: config_entries.ConfigEntry):
    """Set up config entry."""
    entries = hass.data[DOMAIN_DATA_ENTRIES]
    tasks = hass.data[DOMAIN_DATA_TASKS]

    client = Client(entry.data[CONF_HOST], entry.data[CONF_PORT])
    entries[entry.entry_id] = client

    task = asyncio.create_task(_run_client(hass, client, DEFAULT_SCAN_INTERVAL))
    tasks[entry.entry_id] = task

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "media_player")
    )

    return True


async def async_unload_entry(hass, entry):
    """Cleanup before removing config entry."""
    await hass.config_entries.async_forward_entry_unload(entry, "media_player")

    task = hass.data[DOMAIN_DATA_TASKS].pop(entry.entry_id)
    await _await_cancel(task)

    hass.data[DOMAIN_DATA_ENTRIES].pop(entry.entry_id)

    return True


async def _run_client(hass, client, interval):
    def _listen(_):
        hass.helpers.dispatcher.async_dispatcher_send(SIGNAL_CLIENT_DATA, client.host)

    while True:
        try:
            with async_timeout.timeout(interval):
                await client.start()

            _LOGGER.debug("Client connected %s", client.host)
            hass.helpers.dispatcher.async_dispatcher_send(
                SIGNAL_CLIENT_STARTED, client.host
            )

            try:
                with client.listen(_listen):
                    await client.process()
            finally:
                await client.stop()

                _LOGGER.debug("Client disconnected %s", client.host)
                hass.helpers.dispatcher.async_dispatcher_send(
                    SIGNAL_CLIENT_STOPPED, client.host
                )

        except ConnectionFailed:
            await asyncio.sleep(interval)
        except asyncio.TimeoutError:
            continue
        except asyncio.CancelledError:
            raise
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception, aborting arcam client")
            return
