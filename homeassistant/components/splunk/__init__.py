"""Support to send data to a Splunk instance."""
from collections import deque
import json
import logging
import time

from requests import exceptions as request_exceptions
from splunk_data_sender import SplunkSender
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
from homeassistant.helpers import state as state_helper
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import FILTER_SCHEMA
from homeassistant.helpers.json import JSONEncoder

_LOGGER = logging.getLogger(__name__)

DOMAIN = "splunk"
CONF_FILTER = "filter"
SPLUNK_ENDPOINT = "collector/event"
SPLUNK_SIZE_LIMIT = 102400  # 100KB, Actual limit is 512KB

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


def setup(hass, config):
    """Set up the Splunk component."""
    conf = config[DOMAIN]
    host = conf.get(CONF_HOST)
    port = conf.get(CONF_PORT)
    token = conf.get(CONF_TOKEN)
    use_ssl = conf[CONF_SSL]
    verify_ssl = conf.get(CONF_VERIFY_SSL)
    name = conf.get(CONF_NAME)
    entity_filter = conf[CONF_FILTER]

    event_collector = SplunkSender(
        host=host,
        port=port,
        token=token,
        hostname=name,
        protocol=["http", "https"][use_ssl],
        verify=(use_ssl and verify_ssl),
        api_url=SPLUNK_ENDPOINT,
    )

    payload = {
        "time": time.time(),
        "host": name,
        "event": {
            "domain": DOMAIN,
            "meta": "Splunk integration has started",
        },
    }

    try:
        event_collector._send_to_splunk(  # pylint: disable=protected-access
            "send-event", json.dumps(payload)
        )
    except request_exceptions.HTTPError as err:
        if err.response.status_code in (401, 403):
            _LOGGER.error("Invalid or disabled token")
            return False
        _LOGGER.warning(err)
    except (
        request_exceptions.Timeout,
        request_exceptions.ConnectionError,
        request_exceptions.TooManyRedirects,
        json.decoder.JSONDecodeError,
    ) as err:
        _LOGGER.warning(err)

    batch = deque()
    post_in_progress = False

    def splunk_event_listener(event):
        """Listen for new messages on the bus and sends them to Splunk."""
        nonlocal batch
        nonlocal post_in_progress

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
        batch.append(json.dumps(payload, cls=JSONEncoder))

        # Enforce only one loop is running
        if not post_in_progress:
            post_in_progress = True
            # Run until there are no new events to sent
            while batch:
                size = len(batch[0])
                events = deque()
                # Do Until loop to get events until maximum payload size or no more events
                # Ensures at least 1 event is always sent even if it exceeds the size limit
                while True:
                    # Add first event
                    events.append(batch.popleft())
                    # Stop if no more events
                    if not batch:
                        break
                    # Add size of next event
                    size += len(batch[0])
                    # Stop if next event exceeds limit
                    if size > SPLUNK_SIZE_LIMIT:
                        break
                _LOGGER.debug(
                    "Sending %s of %s events", len(events), len(events) + len(batch)
                )
                # Send the selected events
                try:
                    event_collector._send_to_splunk(  # pylint: disable=protected-access
                        "send-event", "\n".join(events)
                    )
                except (
                    request_exceptions.HTTPError,
                    request_exceptions.Timeout,
                    request_exceptions.ConnectionError,
                    request_exceptions.TooManyRedirects,
                ) as err:
                    _LOGGER.warning(err)
                    # Requeue failed events
                    batch = events + batch
                    break
                except json.decoder.JSONDecodeError:
                    _LOGGER.warning("Unexpected response")
                    # Requeue failed events
                    batch = events + batch
                    break
            post_in_progress = False

    hass.bus.listen(EVENT_STATE_CHANGED, splunk_event_listener)

    return True
