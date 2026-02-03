"""Support for sending data to Datadog."""

import logging

from datadog import DogStatsd, initialize

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_PREFIX,
    EVENT_LOGBOOK_ENTRY,
    EVENT_STATE_CHANGED,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, state as state_helper

from . import config_flow as config_flow
from .const import CONF_RATE, DOMAIN

_LOGGER = logging.getLogger(__name__)

type DatadogConfigEntry = ConfigEntry[DogStatsd]

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


async def async_setup_entry(hass: HomeAssistant, entry: DatadogConfigEntry) -> bool:
    """Set up Datadog from a config entry."""

    data = entry.data
    options = entry.options
    host = data[CONF_HOST]
    port = data[CONF_PORT]
    prefix = options[CONF_PREFIX]
    sample_rate = options[CONF_RATE]

    statsd_client = DogStatsd(
        host=host, port=port, namespace=prefix, disable_telemetry=True
    )
    entry.runtime_data = statsd_client

    initialize(statsd_host=host, statsd_port=port)

    def logbook_entry_listener(event):
        name = event.data.get("name")
        message = event.data.get("message")

        entry.runtime_data.event(
            title="Home Assistant",
            message=f"%%% \n **{name}** {message} \n %%%",
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

    entry.async_on_unload(
        hass.bus.async_listen(EVENT_LOGBOOK_ENTRY, logbook_entry_listener)
    )
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_STATE_CHANGED, state_changed_listener)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DatadogConfigEntry) -> bool:
    """Unload a Datadog config entry."""
    runtime = entry.runtime_data
    runtime.flush()
    runtime.close_socket()
    return True
