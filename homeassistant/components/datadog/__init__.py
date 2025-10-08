"""Support for sending data to Datadog."""

import logging

from datadog import DogStatsd, initialize
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
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
from homeassistant.helpers.typing import ConfigType

from . import config_flow as config_flow
from .const import (
    CONF_RATE,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_PREFIX,
    DEFAULT_RATE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

type DatadogConfigEntry = ConfigEntry[DogStatsd]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_PREFIX, default=DEFAULT_PREFIX): cv.string,
                vol.Optional(CONF_RATE, default=DEFAULT_RATE): vol.All(
                    vol.Coerce(int), vol.Range(min=1)
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Datadog integration from YAML, initiating config flow import."""
    if DOMAIN not in config:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config[DOMAIN],
        )
    )

    return True


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
