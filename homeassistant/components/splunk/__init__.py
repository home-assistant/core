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
from homeassistant.core import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    Event,
    EventStateChangedData,
    HomeAssistant,
)
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    issue_registry as ir,
    state as state_helper,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entityfilter import FILTER_SCHEMA, EntityFilter
from homeassistant.helpers.json import JSONEncoder
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import (
    CONF_FILTER,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

DATA_FILTER: HassKey[EntityFilter] = HassKey(DOMAIN)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_TOKEN): cv.string,
                vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
                vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(CONF_FILTER, default={}): FILTER_SCHEMA,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Splunk component from YAML.

    Stores the entity filter in hass.data for use by config entry setup.
    Triggers config entry import for connection settings (with deprecation warning).
    Filter-only YAML configs are allowed without deprecation.
    """
    if DOMAIN not in config:
        # No YAML config - store empty filter for config entry to use
        # Use setdefault to avoid overwriting a filter set for testing
        hass.data.setdefault(DATA_FILTER, FILTER_SCHEMA({}))
        return True

    conf = config[DOMAIN]

    # Store the entity filter in hass.data for async_setup_entry to use
    hass.data[DATA_FILTER] = conf.pop(CONF_FILTER)

    # Check if YAML has connection settings (anything beyond filter)
    # If only filter is configured, no deprecation warning is needed
    if CONF_TOKEN in conf:
        # Trigger import of connection settings to config entry
        hass.async_create_task(_async_import_yaml(hass, conf))
    # If only filter, no import needed - filter is stored and will be used

    return True


async def _async_import_yaml(hass: HomeAssistant, conf: dict[str, Any]) -> None:
    """Import YAML config and create deprecation issues."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=conf,
    )

    if result.get("type") is FlowResultType.ABORT and result.get("reason") not in (
        "already_configured",
        "single_instance_allowed",
    ):
        # Import failed with error - create error-specific issue
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result.get('reason')}",
            breaks_in_ha_version="2026.9.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{result.get('reason')}",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Splunk",
            },
        )
        return

    # Import succeeded or already configured - create standard deprecation issue
    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2026.9.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Splunk",
        },
    )


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
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="connection_error",
            translation_placeholders={
                "host": host,
                "port": str(port),
                "error": str(err),
            },
        ) from err
    except TimeoutError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="timeout_connect",
            translation_placeholders={"host": host, "port": str(port)},
        ) from err
    except Exception as err:
        _LOGGER.exception("Unexpected error setting up Splunk")
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="unexpected_error",
            translation_placeholders={
                "host": host,
                "port": str(port),
                "error": str(err),
            },
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
