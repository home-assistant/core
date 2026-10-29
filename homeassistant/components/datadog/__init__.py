"""Support for sending data to Datadog."""

import asyncio
from collections.abc import Callable
import logging
from typing import Any

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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, state as state_helper
from homeassistant.helpers.event import async_track_time_interval

from . import config_flow as config_flow
from .const import (
    CONF_RATE,
    CONF_RESEND_UNCHANGED,
    DEFAULT_RESEND_UNCHANGED,
    DOMAIN,
    SEND_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

type DatadogConfigEntry = ConfigEntry[DogStatsd]

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


async def async_setup_entry(hass: HomeAssistant, entry: DatadogConfigEntry) -> None:
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

    queue: list[tuple[Callable[..., None], tuple[Any, ...]]] = []
    sending: asyncio.Task[None] | None = None

    def run_sends(sends):
        for target, args in sends:
            target(*args)

    async def drain_queue():
        while queue:
            sends = queue.copy()
            queue.clear()
            await hass.async_add_executor_job(run_sends, sends)

    # Sends run in queue order from one executor job at a time, so a resend
    # can't overwrite a newer value and the client is closed after the last send.
    @callback
    def queue_send(target, *args):
        nonlocal sending
        queue.append((target, args))
        if sending is None or sending.done():
            sending = entry.async_create_task(hass, drain_queue())

    def close_client():
        statsd_client.flush()
        statsd_client.close_socket()

    async def async_close_client():
        if sending is not None:
            await asyncio.wait([sending])
        await hass.async_add_executor_job(close_client)

    # Registered first so it runs last, after the listeners and timer are removed.
    entry.async_on_unload(async_close_client)

    def send_logbook_entry(event):
        name = event.data.get("name")
        message = event.data.get("message")

        statsd_client.event(
            title="Home Assistant",
            message=f"%%% \n **{name}** {message} \n %%%",
            tags=[
                f"entity:{event.data.get('entity_id')}",
                f"domain:{event.data.get('domain')}",
            ],
        )

    def send_state(state):
        if state is None or state.state == STATE_UNKNOWN:
            return

        metric = f"{prefix}.{state.domain}"
        tags = [f"entity:{state.entity_id}"]

        for key, value in state.attributes.items():
            if isinstance(value, (float, int, bool)):
                value = int(value) if isinstance(value, bool) else value
                attribute = f"{metric}.{key.replace(' ', '_')}"
                statsd_client.gauge(
                    attribute, value, sample_rate=sample_rate, tags=tags
                )

        try:
            value = state_helper.state_as_number(state)
            statsd_client.gauge(metric, value, sample_rate=sample_rate, tags=tags)
        except ValueError:
            pass

    def send_states(states):
        for state in states:
            send_state(state)

    @callback
    def logbook_entry_listener(event):
        queue_send(send_logbook_entry, event)

    @callback
    def state_changed_listener(event):
        queue_send(send_state, event.data.get("new_state"))

    # Resend unchanged states so Datadog does not show gaps for stable values.
    @callback
    def send_all_states(now):
        # Skip if the previous resend is still waiting to be sent.
        if all(target is not send_states for target, _ in queue):
            queue_send(send_states, hass.states.async_all())

    entry.async_on_unload(
        hass.bus.async_listen(EVENT_LOGBOOK_ENTRY, logbook_entry_listener)
    )
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_STATE_CHANGED, state_changed_listener)
    )
    if options.get(CONF_RESEND_UNCHANGED, DEFAULT_RESEND_UNCHANGED):
        entry.async_on_unload(
            async_track_time_interval(
                hass, send_all_states, SEND_INTERVAL, cancel_on_shutdown=True
            )
        )


async def async_unload_entry(hass: HomeAssistant, entry: DatadogConfigEntry) -> None:
    """Unload a Datadog config entry."""
    # The client is closed by an unload callback once queued sends finish.
