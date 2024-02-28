"""Support to send data to a Splunk instance."""
from http import HTTPStatus
import json
import logging
import time

from aiohttp import ClientConnectionError, ClientResponseError
from hass_splunk import SplunkPayloadError, hass_splunk
import voluptuous as vol

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
    """Set up the Splunk component."""
    conf = config[DOMAIN]
    host = conf.get(CONF_HOST)
    port = conf.get(CONF_PORT)
    token = conf.get(CONF_TOKEN)
    use_ssl = conf[CONF_SSL]
    verify_ssl = conf.get(CONF_VERIFY_SSL)
    name = conf.get(CONF_NAME)
    entity_filter = conf[CONF_FILTER]

    event_collector = hass_splunk(
        session=async_get_clientsession(hass),
        host=host,
        port=port,
        token=token,
        use_ssl=use_ssl,
        verify_ssl=verify_ssl,
    )

    if not await event_collector.check(connectivity=False, token=True, busy=False):
        return False

    payload = {
        "time": time.time(),
        "host": name,
        "event": {
            "domain": DOMAIN,
            "meta": "Splunk integration has started",
        },
    }

    await event_collector.queue(json.dumps(payload, cls=JSONEncoder), send=False)

    async def splunk_event_listener(event):
        """Listen for new messages on the bus and sends them to Splunk."""

        state = event.data.get("new_state")
        if state is None or not entity_filter(state.entity_id):
            return

        try:
            _state = state_helper.state_as_number(state)
        except ValueError:
            _state = state.state

        payload = {
            "time": event.time_fired.timestamp(),
            "host": name,
            "event": {
                "domain": state.domain,
                "entity_id": state.object_id,
                "attributes": dict(state.attributes),
                "value": _state,
            },
        }

        try:
            await event_collector.queue(json.dumps(payload, cls=JSONEncoder), send=True)
        except SplunkPayloadError as err:
            if err.status == HTTPStatus.UNAUTHORIZED:
                _LOGGER.error(err)
            else:
                _LOGGER.warning(err)
        except ClientConnectionError as err:
            _LOGGER.warning(err)
        except TimeoutError:
            _LOGGER.warning("Connection to %s:%s timed out", host, port)
        except ClientResponseError as err:
            _LOGGER.error(err.message)

    hass.bus.async_listen(EVENT_STATE_CHANGED, splunk_event_listener)

    return True
