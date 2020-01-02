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
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_ZONE,
    EVENT_HOMEASSISTANT_STOP,
    SERVICE_TURN_ON,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .config_flow import get_entry_config
from .const import (
    CONF_UUID,
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


ZONES = [1, 2]

ZONE_SCHEMA = vol.Schema({vol.Optional(SERVICE_TURN_ON): cv.SERVICE_SCHEMA})

DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_UUID): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.positive_int,
        vol.Optional(CONF_ZONE, default={zone: ZONE_SCHEMA({}) for zone in ZONES}): {
            vol.In(ZONES): _optional_zone
        },
        vol.Optional(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_int,
    },
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [DEVICE_SCHEMA])}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Set up the component."""
    configs = hass.data.setdefault(DOMAIN_DATA_CONFIG, {})
    if DOMAIN not in config:
        return True

    for device in config[DOMAIN]:
        configs[device[CONF_UUID]] = device
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=device,
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: config_entries.ConfigEntry):
    """Set up an access point from a config entry."""
    entries = hass.data.setdefault(DOMAIN_DATA_ENTRIES, {})

    client = Client(entry.data[CONF_HOST], entry.data[CONF_PORT])
    entries[entry.entry_id] = client

    config = get_entry_config(hass, entry)

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
