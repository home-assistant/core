"""Support to send data to a Splunk instance."""

from http import HTTPStatus
import json
import logging
import time
from typing import Any

from aiohttp import ClientConnectionError, ClientResponseError
from hass_splunk import SplunkPayloadError, hass_splunk
import probatio

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SSL,
    CONF_TOKEN,
    CONF_VERIFY_SSL,
    EVENT_STATE_CHANGED,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, state as state_helper
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entityfilter import FILTER_SCHEMA, EntityFilter
from homeassistant.helpers.json import JSONEncoder
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import CONF_FILTER, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_FILTER: HassKey[EntityFilter] = HassKey(DOMAIN)

CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.All(
            cv.removed(CONF_TOKEN, raise_if_present=False),
            cv.removed(CONF_HOST, raise_if_present=False),
            cv.removed(CONF_PORT, raise_if_present=False),
            cv.removed(CONF_SSL, raise_if_present=False),
            cv.removed(CONF_VERIFY_SSL, raise_if_present=False),
            cv.removed(CONF_NAME, raise_if_present=False),
            probatio.Schema(
                {probatio.Optional(CONF_FILTER, default={}): FILTER_SCHEMA}
            ),
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Splunk component from YAML.

    Stores the entity filter in hass.data for use by config entry setup.
    """
    if DOMAIN not in config:
        # Use setdefault to avoid overwriting a filter set for testing
        hass.data.setdefault(DATA_FILTER, FILTER_SCHEMA({}))
        return True

    hass.data[DATA_FILTER] = config[DOMAIN][CONF_FILTER]

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Splunk from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    token = entry.data[CONF_TOKEN]
    use_ssl = entry.data[CONF_SSL]
    verify_ssl = entry.data[CONF_VERIFY_SSL]
    name = entry.data.get(CONF_NAME) or hass.config.location_name

    # Get the entity filter from hass.data (set by async_setup or empty if no YAML)
    entity_filter: EntityFilter = hass.data.get(DATA_FILTER, FILTER_SCHEMA({}))

    event_collector = hass_splunk(
        session=async_get_clientsession(hass),
        host=host,
        port=port,
        token=token,
        use_ssl=use_ssl,
        verify_ssl=verify_ssl,
    )

    # Validate connectivity and token
    try:
        # Check connectivity first
        connectivity_ok = await event_collector.check(
            connectivity=True, token=False, busy=False
        )
        # Then check token validity (only if connectivity passed)
        token_ok = connectivity_ok and await event_collector.check(
            connectivity=False, token=True, busy=False
        )
    except ClientConnectionError as err:
        _LOGGER.debug("Connection error during setup at %s:%s: %s", host, port, err)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"host": host, "port": str(port)},
        ) from err
    except TimeoutError as err:
        _LOGGER.debug("Timeout during setup at %s:%s: %s", host, port, err)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="timeout_connect",
            translation_placeholders={"host": host, "port": str(port)},
        ) from err
    except Exception as err:
        _LOGGER.exception("Unexpected setup error at %s:%s", host, port)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="unexpected_connect_error",
        ) from err

    if not connectivity_ok:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"host": host, "port": str(port)},
        )
    if not token_ok:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="invalid_auth"
        )

    # Send startup event
    payload: dict[str, Any] = {
        "time": time.time(),
        "host": name,
        "event": {
            "domain": DOMAIN,
            "meta": "Splunk integration has started",
        },
    }

    await event_collector.queue(json.dumps(payload, cls=JSONEncoder), send=False)

    send_failing = False

    def log_send_failure(level: int, message: str, *args: Any) -> None:
        """Log a send failure, demoting it to debug while an outage is open."""
        nonlocal send_failing

        _LOGGER.log(logging.DEBUG if send_failing else level, message, *args)
        send_failing = True

    async def splunk_event_listener(event: Event[EventStateChangedData]) -> None:
        """Listen for new messages on the bus and sends them to Splunk."""
        nonlocal send_failing

        state = event.data.get("new_state")
        if state is None or not entity_filter(state.entity_id):
            return

        _state: float | str
        try:
            _state = state_helper.state_as_number(state)
        except ValueError:
            _state = state.state

        payload: dict[str, Any] = {
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
            sent = await event_collector.queue(
                json.dumps(payload, cls=JSONEncoder), send=True
            )
        except SplunkPayloadError as err:
            if err.status == HTTPStatus.UNAUTHORIZED:
                entry.async_start_reauth(hass)
                log_send_failure(logging.ERROR, "Splunk token unauthorized: %s", err)
            else:
                log_send_failure(logging.WARNING, "Splunk payload error: %s", err)
            return
        except ClientConnectionError as err:
            log_send_failure(
                logging.DEBUG, "Connection error sending to Splunk: %s", err
            )
            return
        except TimeoutError:
            log_send_failure(
                logging.DEBUG, "Timeout sending to Splunk at %s:%s", host, port
            )
            return
        except ClientResponseError as err:
            log_send_failure(logging.WARNING, "Splunk response error: %s", err.message)
            return
        except Exception:
            # Logged in the handler, so the traceback is still available.
            _LOGGER.log(
                logging.DEBUG if send_failing else logging.ERROR,
                "Unexpected error sending event to Splunk",
                exc_info=not send_failing,
            )
            send_failing = True
            return

        if not sent:
            # Coalesced into an in-flight send, which says nothing about
            # whether this event reached Splunk.
            return

        if send_failing:
            _LOGGER.info("Sending events to Splunk has recovered")
            send_failing = False

    # Store the event listener cancellation callback
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_STATE_CHANGED, splunk_event_listener)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # The event listener is automatically removed by async_on_unload
    return True
