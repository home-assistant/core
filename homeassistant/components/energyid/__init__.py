"""The EnergyID integration.

Provides webhook handling and state change uploading to the EnergyID service.
Uses locked async operations to ensure data consistency and respects upload intervals.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging

import aiohttp
from energyid_webhooks import WebhookClientAsync, WebhookPayload

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, EventStateChangedData, HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_ENTITY_ID,
    CONF_METRIC,
    CONF_METRIC_KIND,
    CONF_UNIT,
    CONF_WEBHOOK_URL,
    DEFAULT_DATA_INTERVAL,
    DEFAULT_UPLOAD_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EnergyID from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    # Create the webhook dispatcher
    dispatcher = WebhookDispatcher(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = dispatcher

    # Validate the webhook client
    try:
        await dispatcher.client.get_policy()
    except aiohttp.ClientResponseError as error:
        _LOGGER.error("Could not validate webhook client")
        raise ConfigEntryError from error

    # Register the webhook dispatcher
    async_track_state_change_event(
        hass=hass,
        entity_ids=dispatcher.entity_id,
        action=dispatcher.async_handle_state_change,
        # homeassistant/components/energyid/__init__.py:56: error: Argument "action" to "async_track_state_change_event" has incompatible type "Callable[[Event[Mapping[str, Any]]], Coroutine[Any, Any, bool]]"; expected "Callable[[Event[EventStateChangedData]], Any]"  [arg-type]
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id)
    return True


class WebhookDispatcher:
    """Handles state changes and uploads data to EnergyID.

    Manages webhooks, enforces upload intervals, and handles data validation.
    Uses asyncio locks to prevent concurrent uploads of the same state.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the dispatcher."""
        self.hass = hass
        self.client = WebhookClientAsync(
            webhook_url=entry.data[CONF_WEBHOOK_URL],
            session=async_get_clientsession(hass),
        )
        self.entity_id = entry.data[CONF_ENTITY_ID]
        self.metric = entry.data[CONF_METRIC]
        self.metric_kind = entry.data[CONF_METRIC_KIND]
        self.unit = entry.data[CONF_UNIT]
        self.data_interval = DEFAULT_DATA_INTERVAL
        self.upload_interval = dt.timedelta(seconds=DEFAULT_UPLOAD_INTERVAL)

        self.last_upload: dt.datetime | None = None

        self._upload_lock = asyncio.Lock()

    async def async_handle_state_change(
        self, event: Event[EventStateChangedData]
    ) -> bool:
        """Handle a state change."""
        async with self._upload_lock:
            return await self._async_handle_state_change(event)

    async def _async_handle_state_change(
        self, event: Event[EventStateChangedData]
    ) -> bool:
        """Handle a state change."""
        _LOGGER.debug("Handling state change event %s", event)
        new_state = event.data["new_state"]

        # Check if enough time has passed since the last upload
        if new_state is None or not self.upload_allowed(new_state.last_changed):
            _LOGGER.debug(
                "Not uploading state %s because of last upload %s",
                new_state,
                self.last_upload,
            )
            return False

        # Check if the new state is a valid float
        try:
            value = float(new_state.state)
        except ValueError:
            _LOGGER.error(
                "Error converting state %s to float for entity %s",
                new_state.state,
                self.entity_id,
            )
            return False

        # Upload the new state
        try:
            data: list[list] = [[new_state.last_changed.isoformat(), value]]
            payload = WebhookPayload(
                remote_id=self.entity_id,
                remote_name=new_state.attributes.get("friendly_name", self.entity_id),
                metric=self.metric,
                metric_kind=self.metric_kind,
                unit=self.unit,
                interval=self.data_interval,
                data=data,
            )
            _LOGGER.debug("Uploading data %s", payload)
            await self.client.post_payload(payload)
        except aiohttp.ClientResponseError as e:
            _LOGGER.error("Client response error while saving data %s: %s", payload, e)
            return False
        except aiohttp.ClientConnectionError as e:
            _LOGGER.error(
                "Client connection error while saving data %s: %s", payload, e
            )
            return False
        except aiohttp.ClientError as e:
            _LOGGER.error("Client error while saving data %s: %s", payload, e)
            return False

        # Update the last upload time
        self.last_upload = new_state.last_changed
        _LOGGER.debug("Updated last upload time to %s", self.last_upload)
        return True

    def upload_allowed(self, state_change_time: dt.datetime) -> bool:
        """Check if an upload is allowed."""
        if self.last_upload is None:
            return True

        return state_change_time - self.last_upload > self.upload_interval
