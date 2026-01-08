"""Support to send data to a Splunk instance."""

from __future__ import annotations

from http import HTTPStatus
import json
import logging
import time
from typing import Any

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
from homeassistant.core import Event, EventStateChangedData, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    issue_registry as ir,
    state as state_helper,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entityfilter import FILTER_SCHEMA
from homeassistant.helpers.json import JSONEncoder
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_FILTER,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

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
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    # Check if the configuration includes entity filters
    # FILTER_SCHEMA returns an EntityFilter object - check empty_filter attribute
    entity_filter = conf.get(CONF_FILTER)
    has_filter = entity_filter is not None and not entity_filter.empty_filter

    if has_filter:
        # Create a repair issue for configurations with filters
        ir.async_create_issue(
            hass,
            DOMAIN,
            "deprecated_yaml_with_filter",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_yaml_with_filter",
            translation_placeholders={
                "documentation_url": "https://www.home-assistant.io/integrations/splunk"
            },
        )
        # Continue using YAML setup for configurations with filters
        return await _async_setup_yaml(hass, conf)

    # For configurations without filters, trigger import to config entry
    ir.async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "documentation_url": "https://www.home-assistant.io/integrations/splunk"
        },
    )

    # Remove filter key before import to avoid validation issues
    import_config = {k: v for k, v in conf.items() if k != CONF_FILTER}

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=import_config,
        )
    )

    return True


async def _async_setup_yaml(hass: HomeAssistant, conf: dict[str, Any]) -> bool:
    """Set up Splunk from YAML configuration (for filter support)."""
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

    async def splunk_event_listener(event: Event[EventStateChangedData]) -> None:
        """Listen for new messages on the bus and sends them to Splunk."""
        state = event.data.get("new_state")
        if state is None or not entity_filter(state.entity_id):
            return

        _state: float | str
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Splunk from a config entry."""
    host = entry.data.get(CONF_HOST, DEFAULT_HOST)
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    token = entry.data[CONF_TOKEN]
    use_ssl = entry.data.get(CONF_SSL, DEFAULT_SSL)
    verify_ssl = entry.data.get(CONF_VERIFY_SSL, True)
    name = entry.data.get(CONF_NAME, DEFAULT_NAME)

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
        raise ConfigEntryNotReady(
            f"Connection error connecting to Splunk at {host}:{port}: {err}"
        ) from err
    except TimeoutError as err:
        raise ConfigEntryNotReady(
            f"Timeout connecting to Splunk at {host}:{port}"
        ) from err
    except Exception as err:
        _LOGGER.exception("Unexpected error setting up Splunk")
        raise ConfigEntryNotReady(
            f"Unexpected error connecting to Splunk: {err}"
        ) from err

    if not connectivity_ok:
        raise ConfigEntryNotReady(
            f"Unable to connect to Splunk instance at {host}:{port}"
        )
    if not token_ok:
        raise ConfigEntryAuthFailed("Invalid Splunk token - please reauthenticate")

    # Send startup event
    payload = {
        "time": time.time(),
        "host": name,
        "event": {
            "domain": DOMAIN,
            "meta": "Splunk integration has started",
        },
    }

    await event_collector.queue(json.dumps(payload, cls=JSONEncoder), send=False)

    async def splunk_event_listener(event: Event[EventStateChangedData]) -> None:
        """Listen for new messages on the bus and sends them to Splunk."""
        state = event.data.get("new_state")
        if state is None:
            return

        _state: float | str
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
                _LOGGER.error("Splunk token unauthorized: %s", err)
                # Trigger reauth flow
                entry.async_start_reauth(hass)
            else:
                _LOGGER.warning("Splunk payload error: %s", err)
        except ClientConnectionError as err:
            _LOGGER.debug("Connection error sending to Splunk: %s", err)
        except TimeoutError:
            _LOGGER.debug("Timeout sending to Splunk at %s:%s", host, port)
        except ClientResponseError as err:
            _LOGGER.warning("Splunk response error: %s", err.message)
        except Exception:
            _LOGGER.exception("Unexpected error sending event to Splunk")

    # Store the event listener cancellation callback
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_STATE_CHANGED, splunk_event_listener)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # The event listener is automatically removed by async_on_unload
    return True
