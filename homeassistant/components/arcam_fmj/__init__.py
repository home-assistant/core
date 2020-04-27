"""Arcam component."""
import asyncio
import logging

from arcam.fmj import ConnectionFailed
from arcam.fmj.client import Client
import async_timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_ZONE,
    EVENT_HOMEASSISTANT_STOP,
    SERVICE_TURN_ON,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import (
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    DOMAIN_DATA_CONFIG,
    DOMAIN_DATA_ENTRIES,
    SIGNAL_CLIENT_DATA,
    SIGNAL_CLIENT_STARTED,
    SIGNAL_CLIENT_STOPPED,
)

_LOGGER = logging.getLogger(__name__)


def _optional_zone(value):
    if value:
        return ZONE_SCHEMA(value)
    return ZONE_SCHEMA({})


def _zone_name_validator(config):
    for zone, zone_config in config[CONF_ZONE].items():
        if CONF_NAME not in zone_config:
            zone_config[
                CONF_NAME
            ] = f"{DEFAULT_NAME} ({config[CONF_HOST]}:{config[CONF_PORT]}) - {zone}"
    return config


ZONE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(SERVICE_TURN_ON): cv.SERVICE_SCHEMA,
    }
)

DEVICE_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(CONF_HOST): cv.string,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.positive_int,
            vol.Optional(CONF_ZONE, default={1: _optional_zone(None)}): {
                vol.In([1, 2]): _optional_zone
            },
            vol.Optional(
                CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
            ): cv.positive_int,
        },
        _zone_name_validator,
    )
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [DEVICE_SCHEMA])}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Set up the component."""
    hass.data[DOMAIN_DATA_ENTRIES] = {}
    hass.data[DOMAIN_DATA_CONFIG] = {}

    for device in config[DOMAIN]:
        hass.data[DOMAIN_DATA_CONFIG][(device[CONF_HOST], device[CONF_PORT])] = device

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data={CONF_HOST: device[CONF_HOST], CONF_PORT: device[CONF_PORT]},
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: config_entries.ConfigEntry):
    """Set up an access point from a config entry."""
    client = Client(entry.data[CONF_HOST], entry.data[CONF_PORT])

    config = hass.data[DOMAIN_DATA_CONFIG].get(
        (entry.data[CONF_HOST], entry.data[CONF_PORT]),
        DEVICE_SCHEMA(
            {CONF_HOST: entry.data[CONF_HOST], CONF_PORT: entry.data[CONF_PORT]}
        ),
    )

    hass.data[DOMAIN_DATA_ENTRIES][entry.entry_id] = {
        "client": client,
        "config": config,
    }

    asyncio.ensure_future(_run_client(hass, client, config[CONF_SCAN_INTERVAL]))

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "media_player")
    )

    return True


async def _run_client(hass, client, interval):
    task = asyncio.Task.current_task()
    run = True

    async def _stop(_):
        nonlocal run
        run = False
        task.cancel()
        await task

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop)

    def _listen(_):
        hass.helpers.dispatcher.async_dispatcher_send(SIGNAL_CLIENT_DATA, client.host)

    while run:
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
            return
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception, aborting arcam client")
            return
