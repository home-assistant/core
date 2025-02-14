"""The EnergyID integration.

Provides webhook handling and state change uploading to the EnergyID service.
Uses locked async operations to ensure data consistency and respects upload intervals.
"""

from __future__ import annotations

import asyncio
from asyncio import timeout
import datetime as dt
import logging
from typing import TypeVar

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

T = TypeVar("T", bound=WebhookClientAsync)
EnergyIDConfigEntry = ConfigEntry[T]


async def async_setup_entry(hass: HomeAssistant, entry: EnergyIDConfigEntry) -> bool:
    """Set up EnergyID from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    client = WebhookClientAsync(
        webhook_url=entry.data[CONF_WEBHOOK_URL],
        session=async_get_clientsession(hass),
    )
    try:
        await client.get_policy()
    except aiohttp.ClientResponseError as error:
        _LOGGER.error("Could not validate webhook client")
        raise ConfigEntryError from error

    entry.runtime_data = client

    dispatcher = WebhookDispatcher(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = dispatcher

    if not await dispatcher.async_check_connection():
        _LOGGER.warning(
            "Initial connection to EnergyID webhook service failed. Will retry on state changes"
        )

    async_track_state_change_event(
        hass=hass,
        entity_ids=dispatcher.entity_id,
        action=dispatcher.async_handle_state_change,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: EnergyIDConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id)
    return True


class WebhookDispatcher:
    """Handles state changes and uploads data to EnergyID.

    Manages webhook communication, upload intervals, and data validation.
    Uses asyncio.Lock to prevent concurrent uploads for data consistency.
    """

    def __init__(self, hass: HomeAssistant, entry: EnergyIDConfigEntry) -> None:
        """Initialize the dispatcher."""
        self.hass = hass
        self.client = entry.runtime_data
        self.entity_id = entry.data[CONF_ENTITY_ID]
        self.metric = entry.data[CONF_METRIC]
        self.metric_kind = entry.data[CONF_METRIC_KIND]
        self.unit = entry.data[CONF_UNIT]
        self.data_interval = DEFAULT_DATA_INTERVAL
        self.upload_interval = dt.timedelta(seconds=DEFAULT_UPLOAD_INTERVAL)

        self.last_upload: dt.datetime | None = None
        self._upload_lock = asyncio.Lock()
        self._connected = False

    async def async_check_connection(self) -> bool:
        """Check connection to EnergyID and log status changes."""
        try:
            await self.client.get_policy()
            if not self._connected:
                _LOGGER.info("Successfully connected to EnergyID webhook service")
                self._connected = True
        except (aiohttp.ClientConnectionError, aiohttp.ClientResponseError) as err:
            if self._connected:
                _LOGGER.info("Lost connection to EnergyID webhook service: %s", err)
                self._connected = False
            return False
        else:
            return True

    async def async_handle_state_change(
        self, event: Event[EventStateChangedData]
    ) -> bool:
        """Handle a state change event."""
        if not await self.async_check_connection():
            return False

        async with self._upload_lock:
            return await self._async_handle_state_change(event)

    async def _async_handle_state_change(
        self, event: Event[EventStateChangedData]
    ) -> bool:
        """Process and upload a state change event."""
        _LOGGER.debug("Handling state change event %s", event)
        new_state = event.data["new_state"]

        if new_state is None or not self.upload_allowed(new_state.last_changed):
            _LOGGER.debug(
                "Not uploading state %s due to upload interval or None state",
                new_state,
            )
            return False

        try:
            value = float(new_state.state)
        except ValueError:
            _LOGGER.error(
                "Error converting state %s to float for entity %s",
                new_state.state,
                self.entity_id,
            )
            return False

        retries = 3
        for attempt in range(retries):
            try:
                data: list[list] = [[new_state.last_changed.isoformat(), value]]
                payload = WebhookPayload(
                    remote_id=self.entity_id,
                    remote_name=new_state.attributes.get(
                        "friendly_name", self.entity_id
                    ),
                    metric=self.metric,
                    metric_kind=self.metric_kind,
                    unit=self.unit,
                    interval=self.data_interval,
                    data=data,
                )
                _LOGGER.debug(
                    "Uploading data %s, attempt %s/%s", payload, attempt + 1, retries
                )
                async with timeout(10):
                    await self.client.post_payload(payload)
                break
            except (
                TimeoutError,
                aiohttp.ClientConnectionError,
                aiohttp.ClientResponseError,
                aiohttp.ClientError,
            ) as err:
                _LOGGER.warning(
                    "Upload to EnergyID failed (attempt %s/%s): %s",
                    attempt + 1,
                    retries,
                    err,
                )
                if attempt < retries - 1:
                    delay = 2**attempt
                    _LOGGER.debug("Waiting %s seconds before retrying", delay)
                    await asyncio.sleep(delay)
        else:
            _LOGGER.error(
                "Failed to upload data to EnergyID after %s retries. Payload: %s",
                retries,
                payload,
            )
            return False

        self.last_upload = new_state.last_changed
        _LOGGER.debug("Last upload time updated to %s", self.last_upload)
        return True

    def upload_allowed(self, state_change_time: dt.datetime) -> bool:
        """Check if upload is allowed based on the upload interval."""
        if self.last_upload is None:
            return True
        return state_change_time - self.last_upload > self.upload_interval
