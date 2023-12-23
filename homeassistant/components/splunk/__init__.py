"""Support to send data to a Splunk instance."""
import asyncio
import json
import logging

from aiohttp import ClientConnectionError, ClientResponseError
from hass_splunk import SplunkPayloadError, hass_splunk
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SSL,
    CONF_TOKEN,
    CONF_VERIFY_SSL,
    EVENT_STATE_CHANGED,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import state as state_helper
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import FILTER_SCHEMA
from homeassistant.helpers.json import JSONEncoder
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "splunk"
CONF_FILTER = "filter"

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8088
DEFAULT_SSL = False
DEFAULT_NAME = "HASS"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_TOKEN): cv.string,
                vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_SSL, default=False): cv.boolean,
                vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(CONF_FILTER, default={}): FILTER_SCHEMA,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Old setup for Splunk component."""
    if DOMAIN in config:
        # Entity filters are not configurable in Config Flow, so are removed
        data = {k: v for k, v in config[DOMAIN].items() if k != "filter"}
        _LOGGER.warning(
            "Your Splunk configuration has been imported into the UI; "
            "please remove it from configuration.yaml as support for it "
            "will be removed in a future release"
        )
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=data
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Splunk from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    name = entry.data.get(CONF_NAME)
    splunk = hass_splunk(
        session=async_get_clientsession(hass),
        host=host,
        port=port,
        token=entry.data[CONF_TOKEN],
        use_ssl=entry.data[CONF_SSL],
        verify_ssl=entry.data[CONF_VERIFY_SSL],
    )

    if not await splunk.check(connectivity=False, token=True, busy=False):
        # Authentication failure cannot be recovered from.
        raise ConfigEntryAuthFailed()

    async def splunk_event_listener(event):
        """Listen for new messages on the bus and sends them to Splunk."""

        state = event.data.get("new_state")

        try:
            _state = state_helper.state_as_number(state)
        except ValueError:
            _state = state.state

        payload = {
            "time": event.time_fired.timestamp(),
            "event": {
                "domain": state.domain,
                "entity_id": state.object_id,
                "attributes": dict(state.attributes),
                "value": _state,
            },
        }
        if name:
            payload["host"] = name

        try:
            await splunk.queue(json.dumps(payload, cls=JSONEncoder), send=True)
        except SplunkPayloadError as err:
            _LOGGER.warning(err)
        except ClientConnectionError as err:
            _LOGGER.warning(err)
        except asyncio.TimeoutError:
            _LOGGER.warning("Connection to %s:%s timed out", host, port)
        except ClientResponseError as err:
            _LOGGER.error(err.message)

    hass.bus.async_listen(EVENT_STATE_CHANGED, splunk_event_listener)

    return True
