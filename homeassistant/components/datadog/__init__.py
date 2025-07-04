"""Support for sending data to Datadog."""

import asyncio
import logging

from datadog import DogStatsd, initialize

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_LOGBOOK_ENTRY, EVENT_STATE_CHANGED, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, state as state_helper
from homeassistant.helpers.typing import ConfigType

from .const import DEFAULT_HOST, DEFAULT_PORT, DEFAULT_PREFIX, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type DatadogConfigEntry = ConfigEntry[DogStatsd]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Datadog component from YAML config."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Datadog from a config entry."""

    conf = entry.data
    host = conf.get("host", DEFAULT_HOST)
    port = conf.get("port", DEFAULT_PORT)
    sample_rate = conf.get("rate", 1)
    prefix = conf.get("prefix", DEFAULT_PREFIX)

    statsd_client = DogStatsd(host=host, port=port, namespace=prefix)

    entry.runtime_data = statsd_client

    initialize(statsd_host=host, statsd_port=port)

    def logbook_entry_listener(event):
        name = event.data.get("name")
        message = event.data.get("message")

        entry.runtime_data.event(
            title="Home Assistant",
            text=f"%%% \n **{name}** {message} \n %%%",
            tags=[
                f"entity:{event.data.get('entity_id')}",
                f"domain:{event.data.get('domain')}",
            ],
        )

    def state_changed_listener(event):
        state = event.data.get("new_state")
        if state is None or state.state == STATE_UNKNOWN:
            return

        metric = f"{prefix}.{state.domain}"
        tags = [f"entity:{state.entity_id}"]

        for key, value in state.attributes.items():
            if isinstance(value, (float, int, bool)):
                value = int(value) if isinstance(value, bool) else value
                attribute = f"{metric}.{key.replace(' ', '_')}"
                entry.runtime_data.gauge(
                    attribute, value, sample_rate=sample_rate, tags=tags
                )

        try:
            value = state_helper.state_as_number(state)
            entry.runtime_data.gauge(metric, value, sample_rate=sample_rate, tags=tags)
        except ValueError:
            pass

    hass.bus.async_listen(EVENT_LOGBOOK_ENTRY, logbook_entry_listener)
    hass.bus.async_listen(EVENT_STATE_CHANGED, state_changed_listener)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Datadog config entry."""
    return True


async def validate_datadog_connection(host: str, port: int, prefix: str) -> bool:
    """Attempt to send a test metric to the Datadog agent."""
    statsd_client = DogStatsd(host=host, port=port, namespace=prefix)
    loop = asyncio.get_running_loop()

    try:
        await loop.run_in_executor(None, statsd_client.increment, "connection_test")
    except OSError:
        # Connection issues like ECONNREFUSED
        return False
    except ValueError:
        # Likely a bad host/port/prefix format
        return False
    else:
        return True
