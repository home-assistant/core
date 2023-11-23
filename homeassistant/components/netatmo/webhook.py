"""The Netatmo integration."""
import logging

from aiohttp.web import Request

from homeassistant.const import ATTR_DEVICE_ID, ATTR_ID, ATTR_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue
)

from .const import (
    ATTR_EVENT_TYPE,
    ATTR_FACE_URL,
    ATTR_HOME_ID,
    ATTR_IS_KNOWN,
    ATTR_PERSONS,
    DATA_DEVICE_IDS,
    DATA_PERSONS,
    DEFAULT_PERSON,
    DOMAIN,
    EVENT_ID_MAP,
    ISSUE_ID_WEBHOOK_NOT_REGISTERED,
    ISSUE_ID_WEBHOOK_REGISTRATION_ERROR,
    NETATMO_EVENT,
    WEBHOOK_HELP_LINK,
)

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
        return None

    _LOGGER.debug("Got webhook data: %s", data)

    event_type = data.get(ATTR_EVENT_TYPE)

    if event_type in SUBEVENT_TYPE_MAP:
        async_send_event(hass, event_type, data)

        for event_data in data.get(SUBEVENT_TYPE_MAP[event_type], []):
            async_evaluate_event(hass, event_data)

    else:
        async_evaluate_event(hass, data)


def async_evaluate_event(hass: HomeAssistant, event_data: dict) -> None:
    """Evaluate events from webhook."""
    event_type = event_data.get(ATTR_EVENT_TYPE, "None")

    if event_type == "person":
        for person in event_data.get(ATTR_PERSONS, {}):
            person_event_data = dict(event_data)
            person_event_data[ATTR_ID] = person.get(ATTR_ID)
            person_event_data[ATTR_NAME] = hass.data[DOMAIN][DATA_PERSONS][
                event_data[ATTR_HOME_ID]
            ].get(person_event_data[ATTR_ID], DEFAULT_PERSON)
            person_event_data[ATTR_IS_KNOWN] = person.get(ATTR_IS_KNOWN)
            person_event_data[ATTR_FACE_URL] = person.get(ATTR_FACE_URL)

            async_send_event(hass, event_type, person_event_data)

    else:
        async_send_event(hass, event_type, event_data)


def async_send_event(hass: HomeAssistant, event_type: str, data: dict) -> None:
    """Send events."""
    _LOGGER.debug("%s: %s", event_type, data)
    async_dispatcher_send(
        hass,
        f"signal-{DOMAIN}-webhook-{event_type}",
        {"type": event_type, "data": data},
    )

    event_data = {
        "type": event_type,
        "data": data,
    }

    if event_type in EVENT_ID_MAP:
        data_device_id = data[EVENT_ID_MAP[event_type]]
        event_data[ATTR_DEVICE_ID] = hass.data[DOMAIN][DATA_DEVICE_IDS].get(
            data_device_id
        )

    hass.bus.async_fire(
        event_type=NETATMO_EVENT,
        event_data=event_data,
    )


def async_delete_webhook_issues(hass: HomeAssistant) -> None:
    """Delete all webhook related issues."""
    async_delete_issue_webhook_not_registered(hass)
    async_delete_issue_webhook_registration_error(hass)


def async_create_issue_webhook_not_registered(hass: HomeAssistant) -> None:
    """Create an issue indicating that the webhook has been unregistered."""
    async_create_issue(
        hass,
        DOMAIN,
        ISSUE_ID_WEBHOOK_NOT_REGISTERED,
        is_fixable=False,
        learn_more_url=WEBHOOK_HELP_LINK,
        severity=IssueSeverity.WARNING,
        translation_key=ISSUE_ID_WEBHOOK_NOT_REGISTERED,
    )


def async_delete_issue_webhook_not_registered(hass: HomeAssistant) -> None:
    """Delete the issue indicating that the webhook has been unregistered."""
    async_delete_issue(
        hass,
        DOMAIN,
        ISSUE_ID_WEBHOOK_NOT_REGISTERED,
    )


def async_create_issue_webhook_registration_error(hass: HomeAssistant) -> None:
    """Create an issue indicating that the webhook could not be registered."""
    async_create_issue(
        hass,
        DOMAIN,
        ISSUE_ID_WEBHOOK_REGISTRATION_ERROR,
        is_fixable=False,
        learn_more_url=WEBHOOK_HELP_LINK,
        severity=IssueSeverity.ERROR,
        translation_key=ISSUE_ID_WEBHOOK_REGISTRATION_ERROR,
    )


def async_delete_issue_webhook_registration_error(hass: HomeAssistant) -> None:
    """Delete the issue indicating that the webhook could not be registered."""
    async_delete_issue(
        hass,
        DOMAIN,
        ISSUE_ID_WEBHOOK_REGISTRATION_ERROR,
    )
