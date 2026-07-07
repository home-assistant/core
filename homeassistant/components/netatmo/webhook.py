"""The Netatmo integration."""

import logging
import secrets
from typing import Any

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
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    ATTR_EVENT_TYPE,
    ATTR_FACE_URL,
    ATTR_HOME_ID,
    ATTR_IS_KNOWN,
    CONF_CLOUDHOOK_URL,
    DEFAULT_PERSON,
    DOMAIN,
    EVENT_ID_MAP,
    NETATMO_EVENT,
    WEBHOOK_DEACTIVATION,
    WEBHOOK_PUSH_TYPE,
)
from .data_handler import NetatmoConfigEntry, NetatmoDataHandler

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
        webhook_url = await cloud.async_create_cloudhook(
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
    _LOGGER.debug("Unregister Netatmo webhook (%s)", entry.data[CONF_WEBHOOK_ID])
    async_dispatcher_send(
        hass,
        f"signal-{DOMAIN}-webhook-None",
        {"type": "None", "data": {WEBHOOK_PUSH_TYPE: WEBHOOK_DEACTIVATION}},
    )
    webhook_unregister(hass, entry.data[CONF_WEBHOOK_ID])
    try:
        await entry.runtime_data.auth.async_dropwebhook()
    except pyatmo.ApiError:
        _LOGGER.debug("No webhook to be dropped for %s", entry.data[CONF_WEBHOOK_ID])


async def async_register_webhook(
    hass: HomeAssistant, entry: NetatmoConfigEntry
) -> None:
    """Register the webhook with the Netatmo backend."""
    if CONF_WEBHOOK_ID not in entry.data:
        data = {**entry.data, CONF_WEBHOOK_ID: secrets.token_hex()}
        hass.config_entries.async_update_entry(entry, data=data)

    if cloud.async_active_subscription(hass):
        webhook_url = await async_cloudhook_generate_url(hass, entry)
    else:
        webhook_url = webhook_generate_url(hass, entry.data[CONF_WEBHOOK_ID])

    if entry.data["auth_implementation"] == cloud.DOMAIN and not webhook_url.startswith(
        "https://"
    ):
        _LOGGER.warning(
            "Webhook not registered - "
            "https and port 443 is required to register the webhook"
        )
        return

    webhook_register(
        hass,
        DOMAIN,
        "Netatmo",
        entry.data[CONF_WEBHOOK_ID],
        async_handle_webhook,
    )

    async def _handle_stop(_: Event) -> None:
        await async_unregister_webhook(hass, entry)

    try:
        await entry.runtime_data.auth.async_addwebhook(webhook_url)
        _LOGGER.debug("Register Netatmo webhook: %s", webhook_url)
    # pylint: disable-next=home-assistant-action-swallowed-exception
    except pyatmo.ApiError as err:
        webhook_unregister(hass, entry.data[CONF_WEBHOOK_ID])
        _LOGGER.error("Error during webhook registration - %s", err)
    else:
        entry.async_on_unload(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _handle_stop)
        )
