"""Sendspin pairing support.

Tracks the Sendspin client ids of the connected devices, so a Sendspin server
(Music Assistant) can learn which of its clients it can pair with the token the
device hands out over the native API.
"""

from collections.abc import Callable
from datetime import datetime
from functools import partial
import logging
from typing import cast

from aioesphomeapi import APIConnectionError, DeviceCapabilities
from aioesphomeapi.model import SendspinFeature

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from .domain_data import DomainData
from .entry_data import ESPHomeConfigEntry, RuntimeEntryData

_LOGGER = logging.getLogger(__name__)

# The client id stays empty until the device's Sendspin client has started, which
# may be well after the capabilities were fetched on connect, so keep asking.
CLIENT_ID_RETRY_DELAY = 5
CLIENT_ID_RETRY_MAX_DELAY = 300

type SendspinClientsCallback = Callable[[list[str]], None]


@callback
def async_sendspin_client_ids(hass: HomeAssistant) -> list[str]:
    """Return the client ids of the connected devices that hand out a pairing token."""
    return sorted(DomainData.get(hass).sendspin_client_ids)


@callback
def async_subscribe_sendspin_clients(
    hass: HomeAssistant, subscriber: SendspinClientsCallback
) -> CALLBACK_TYPE:
    """Call the subscriber with the client ids whenever they change."""
    subscribers = DomainData.get(hass).sendspin_subscribers
    subscribers.add(subscriber)
    return partial(subscribers.discard, subscriber)


@callback
def async_sendspin_entry_data(
    hass: HomeAssistant, client_id: str
) -> RuntimeEntryData | None:
    """Return the connected device with this Sendspin client id."""
    if (entry_id := DomainData.get(hass).sendspin_client_ids.get(client_id)) is None:
        return None
    entry = cast(ESPHomeConfigEntry, hass.config_entries.async_get_entry(entry_id))
    return entry.runtime_data


@callback
def async_sendspin_on_connect(
    hass: HomeAssistant, entry_data: RuntimeEntryData
) -> None:
    """Start tracking the Sendspin client id of a device that just connected."""
    assert entry_data.device_capabilities is not None
    sendspin = entry_data.device_capabilities.sendspin
    if not sendspin.feature_flags & SendspinFeature.PAIRING_TOKEN:
        return
    entry_data.disconnect_callbacks.add(
        partial(_async_forget_client_id, hass, entry_data)
    )
    if sendspin.client_id:
        _async_set_client_id(hass, entry_data, sendspin.client_id)
    else:
        _async_schedule_client_id_refresh(hass, entry_data, CLIENT_ID_RETRY_DELAY)


@callback
def _async_set_client_id(
    hass: HomeAssistant, entry_data: RuntimeEntryData, client_id: str
) -> None:
    client_ids = DomainData.get(hass).sendspin_client_ids
    if client_ids.get(client_id) == entry_data.entry_id:
        return
    client_ids[client_id] = entry_data.entry_id
    _async_notify_subscribers(hass)


@callback
def _async_forget_client_id(hass: HomeAssistant, entry_data: RuntimeEntryData) -> None:
    # the tracked id is the one in the cached capabilities, which outlive the connection
    assert entry_data.device_capabilities is not None
    client_id = entry_data.device_capabilities.sendspin.client_id
    client_ids = DomainData.get(hass).sendspin_client_ids
    if client_id and client_ids.get(client_id) == entry_data.entry_id:
        del client_ids[client_id]
        _async_notify_subscribers(hass)


@callback
def _async_notify_subscribers(hass: HomeAssistant) -> None:
    client_ids = async_sendspin_client_ids(hass)
    for subscriber in DomainData.get(hass).sendspin_subscribers.copy():
        subscriber(client_ids)


@callback
def _async_schedule_client_id_refresh(
    hass: HomeAssistant, entry_data: RuntimeEntryData, delay: float
) -> None:
    """Fetch the capabilities again later, until they carry the client id."""

    async def _async_refresh(_now: datetime) -> None:
        # The disconnect callbacks are replaced on every disconnect, so the set
        # identifies the connection this refresh was scheduled for
        session = entry_data.disconnect_callbacks
        session.discard(cancel)
        next_delay = min(delay * 2, CLIENT_ID_RETRY_MAX_DELAY)
        try:
            capabilities = await entry_data.client.device_capabilities()
        except APIConnectionError as err:
            if entry_data.disconnect_callbacks is session:
                # still connected: the device did not answer in time, ask again later
                _LOGGER.debug("%s: capabilities unavailable: %s", entry_data.name, err)
                _async_schedule_client_id_refresh(hass, entry_data, next_delay)
            return
        if entry_data.disconnect_callbacks is not session:
            # the device dropped off meanwhile; the next connect starts over
            return
        # Only the Sendspin part is taken: the cache may have been patched with
        # newer data, like a Z-Wave home id change, while the request was out
        assert entry_data.device_capabilities is not None
        merged = entry_data.device_capabilities.to_dict()
        merged["sendspin"] = capabilities.sendspin.to_dict()
        entry_data.device_capabilities = DeviceCapabilities.from_dict(merged)
        entry_data.async_save_to_store()
        if client_id := capabilities.sendspin.client_id:
            _async_set_client_id(hass, entry_data, client_id)
        else:
            _async_schedule_client_id_refresh(hass, entry_data, next_delay)

    cancel = async_call_later(hass, delay, _async_refresh)
    entry_data.disconnect_callbacks.add(cancel)
