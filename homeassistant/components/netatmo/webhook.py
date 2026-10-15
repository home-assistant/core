"""The Netatmo integration."""

import asyncio
import logging
import secrets
from typing import Any

import aiohttp
from aiohttp.web import Request
import pyatmo

from homeassistant.components import cloud
from homeassistant.components.webhook import (
    async_generate_url as webhook_generate_url,
    async_register as webhook_register,
    async_unregister as webhook_unregister,
)
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_ID,
    ATTR_NAME,
    ATTR_PERSONS,
    CONF_WEBHOOK_ID,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later

from .const import (
    ATTR_EVENT_TYPE,
    ATTR_FACE_URL,
    ATTR_HOME_ID,
    ATTR_IS_KNOWN,
    CONF_CLOUDHOOK_URL,
    DEFAULT_PERSON,
    DOMAIN,
    EVENT_ID_MAP,
    MAX_WEBHOOK_RETRY_DELAY,
    NETATMO_EVENT,
    WEBHOOK_DEACTIVATION,
    WEBHOOK_PUSH_TYPE,
    WEBHOOK_RETRY_DELAY,
)
from .coordinator import NetatmoConfigEntry, NetatmoDataHandler

_LOGGER = logging.getLogger(__name__)

SUBEVENT_TYPE_MAP = {
    "outdoor": "",
    "therm_mode": "",
}


async def async_handle_webhook(
    hass: HomeAssistant, webhook_id: str, request: Request
) -> None:
    """Handle webhook callback."""
    try:
        data = await request.json()
    except ValueError as err:
        _LOGGER.error("Error in data: %s", err)
        return

    _LOGGER.debug("Got webhook data: %s", data)

    entry = next(
        (
            entry
            for entry in hass.config_entries.async_loaded_entries(DOMAIN)
            if entry.data.get(CONF_WEBHOOK_ID) == webhook_id
        ),
        None,
    )
    if entry is None:
        return
    data_handler = entry.runtime_data

    event_type = data.get(ATTR_EVENT_TYPE)

    if event_type in SUBEVENT_TYPE_MAP:
        async_send_event(data_handler, event_type, data)

        for event_data in data.get(SUBEVENT_TYPE_MAP[event_type], []):
            async_evaluate_event(data_handler, event_data)

    else:
        async_evaluate_event(data_handler, data)


def async_evaluate_event(data_handler: NetatmoDataHandler, event_data: dict) -> None:
    """Evaluate events from webhook."""
    event_type = event_data.get(ATTR_EVENT_TYPE, "None")

    if event_type == "person":
        for person in event_data.get(ATTR_PERSONS, {}):
            person_event_data = dict(event_data)
            person_event_data[ATTR_ID] = person.get(ATTR_ID)
            person_event_data[ATTR_NAME] = data_handler.persons[
                event_data[ATTR_HOME_ID]
            ].get(person_event_data[ATTR_ID], DEFAULT_PERSON)
            person_event_data[ATTR_IS_KNOWN] = person.get(ATTR_IS_KNOWN)
            person_event_data[ATTR_FACE_URL] = person.get(ATTR_FACE_URL)

            async_send_event(data_handler, event_type, person_event_data)

    else:
        async_send_event(data_handler, event_type, event_data)


def async_send_event(
    data_handler: NetatmoDataHandler, event_type: str, data: dict
) -> None:
    """Send events."""
    hass = data_handler.hass
    _LOGGER.debug("%s: %s", event_type, data)
    async_dispatcher_send(
        hass,
        f"signal-{DOMAIN}-webhook-{event_type}",
        {"type": event_type, "data": data},
    )

    event_data: dict[str, Any] = {
        "type": event_type,
        "data": data,
    }

    if event_type in EVENT_ID_MAP:
        data_device_id = data[EVENT_ID_MAP[event_type]]
        event_data[ATTR_DEVICE_ID] = data_handler.device_ids.get(data_device_id)

    hass.bus.async_fire(
        event_type=NETATMO_EVENT,
        event_data=event_data,
    )


async def async_cloudhook_generate_url(
    hass: HomeAssistant, entry: NetatmoConfigEntry
) -> str:
    """Generate the full URL for a webhook_id."""
    if CONF_CLOUDHOOK_URL not in entry.data:
        # Get or create: the cloud can still hold a hook this entry lost track of,
        # and creating a second one for the same id is refused outright
        webhook_url = await cloud.async_get_or_create_cloudhook(
            hass, entry.data[CONF_WEBHOOK_ID]
        )
        data = {**entry.data, CONF_CLOUDHOOK_URL: webhook_url}
        hass.config_entries.async_update_entry(entry, data=data)
        return webhook_url
    return str(entry.data[CONF_CLOUDHOOK_URL])


async def async_unregister_webhook(
    hass: HomeAssistant, entry: NetatmoConfigEntry
) -> None:
    """Unregister the webhook from the Netatmo backend."""
    if CONF_WEBHOOK_ID not in entry.data:
        return

    if not entry.runtime_data.webhook_registered:
        return

    entry.runtime_data.webhook_registered = False

    _LOGGER.debug("Unregister Netatmo webhook (%s)", entry.data[CONF_WEBHOOK_ID])
    async_dispatcher_send(
        hass,
        f"signal-{DOMAIN}-webhook-None",
        {"type": "None", "data": {WEBHOOK_PUSH_TYPE: WEBHOOK_DEACTIVATION}},
    )

    webhook_unregister(hass, entry.data[CONF_WEBHOOK_ID])

    try:
        await entry.runtime_data.auth.async_dropwebhook()
    except pyatmo.ApiError, TimeoutError, aiohttp.ClientError:
        _LOGGER.debug("No webhook to be dropped for %s", entry.data[CONF_WEBHOOK_ID])


async def async_register_webhook(
    hass: HomeAssistant, entry: NetatmoConfigEntry
) -> bool:
    """Register the webhook with the Netatmo backend.

    Return whether the registration is settled, which a caller that retries needs
    to know. A URL that cannot work is settled without having been registered:
    trying again cannot help until the configuration changes. A URL that cannot be
    built yet is the opposite - unsettled, so that the caller tries again.
    """
    if CONF_WEBHOOK_ID not in entry.data:
        data = {**entry.data, CONF_WEBHOOK_ID: secrets.token_hex()}
        hass.config_entries.async_update_entry(entry, data=data)

    if cloud.async_active_subscription(hass):
        try:
            webhook_url = await async_cloudhook_generate_url(hass, entry)
        except cloud.CloudNotAvailable:
            # The cloud can drop out between the caller's check and this call
            _LOGGER.debug("No cloudhook to register yet")
            return False
    else:
        webhook_url = webhook_generate_url(hass, entry.data[CONF_WEBHOOK_ID])

    if entry.data["auth_implementation"] == cloud.DOMAIN and not webhook_url.startswith(
        "https://"
    ):
        _LOGGER.warning(
            "Webhook not registered - "
            "https and port 443 is required to register the webhook"
        )
        return True

    webhook_unregister(hass, entry.data[CONF_WEBHOOK_ID])
    webhook_register(
        hass,
        DOMAIN,
        "Netatmo",
        entry.data[CONF_WEBHOOK_ID],
        async_handle_webhook,
    )
    entry.runtime_data.webhook_registered = True

    try:
        await entry.runtime_data.auth.async_addwebhook(webhook_url)
    except (pyatmo.ApiError, TimeoutError, aiohttp.ClientError) as err:
        _LOGGER.error("Error during webhook registration - %s", err)
        return False
    else:
        _LOGGER.debug("Register Netatmo webhook: %s", webhook_url)
        return True


class NetatmoWebhookManager:
    """Keep the Netatmo webhook registered for as long as the entry is loaded.

    Registering, retrying and dropping all act on the one registration Netatmo
    holds for the account, so they take a lock. A drop that overtakes the
    registration it is meant to undo leaves Netatmo delivering to a webhook Home
    Assistant no longer answers, and the failed deliveries suspend the URL.
    """

    def __init__(self, hass: HomeAssistant, entry: NetatmoConfigEntry) -> None:
        """Initialize the webhook manager."""
        self.hass = hass
        self.entry = entry
        self._register_lock = asyncio.Lock()
        self._registered = False
        self._attempt_delay = WEBHOOK_RETRY_DELAY
        self._cancel_attempt: CALLBACK_TYPE | None = None

    @callback
    def cancel_pending_attempt(self) -> None:
        """Drop a scheduled registration attempt, if one is pending."""
        if self._cancel_attempt is not None:
            self._cancel_attempt()
            self._cancel_attempt = None

    @callback
    def _schedule_attempt(self) -> None:
        """Arm the next attempt, replacing any already pending."""
        self.cancel_pending_attempt()
        self._cancel_attempt = async_call_later(
            self.hass, self._attempt_delay, self.async_ensure_registered
        )

    async def async_ensure_registered(self, _: Any = None) -> None:
        """Register the webhook, and keep trying until it sticks."""
        async with self._register_lock:
            self.cancel_pending_attempt()
            if self._registered:
                return

            # Registering while the cloud is down points Netatmo at an endpoint
            # that cannot answer, and the failed deliveries suspend the URL
            settled = False
            if not cloud.async_active_subscription(
                self.hass
            ) or cloud.async_is_connected(self.hass):
                settled = await async_register_webhook(self.hass, self.entry)

            if settled:
                self._registered = True
                self._attempt_delay = WEBHOOK_RETRY_DELAY
                return

            self._schedule_attempt()
            self._attempt_delay = min(self._attempt_delay * 2, MAX_WEBHOOK_RETRY_DELAY)

    async def async_unregister(self, _: Any = None) -> None:
        """Drop the webhook, waiting out a registration still in flight."""
        async with self._register_lock:
            self.cancel_pending_attempt()
            self._registered = False
            await async_unregister_webhook(self.hass, self.entry)

    async def async_handle_cloud_state(self, state: cloud.CloudConnectionState) -> None:
        """Follow the cloud connection the webhook URL is delivered over."""
        self._attempt_delay = WEBHOOK_RETRY_DELAY

        if state is cloud.CloudConnectionState.CLOUD_CONNECTED:
            await self.async_ensure_registered()

        if state is cloud.CloudConnectionState.CLOUD_DISCONNECTED:
            await self.async_unregister()
            self._schedule_attempt()
