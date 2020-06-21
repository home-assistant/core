"""The Netatmo integration."""
import logging

from homeassistant.core import callback

from .const import (
    ATTR_EVENT_TYPE,
    ATTR_FACE_URL,
    ATTR_ID,
    ATTR_IS_KNOWN,
    ATTR_NAME,
    ATTR_PERSONS,
    DATA_PERSONS,
    DEFAULT_PERSON,
    DOMAIN,
    NETATMO_EVENT,
)

_LOGGER = logging.getLogger(__name__)


async def handle_webhook(hass, webhook_id, request):
    """Handle webhook callback."""
    try:
        data = await request.json()
    except ValueError:
        return None

    _LOGGER.debug("Got webhook data: %s", data)

    event_type = data.get(ATTR_EVENT_TYPE)

    if event_type == "outdoor":
        hass.bus.async_fire(
            event_type=NETATMO_EVENT, event_data={"type": event_type, "data": data}
        )
        for event_data in data.get("event_list"):
            async_evaluate_event(hass, event_data)
    else:
        async_evaluate_event(hass, data)


@callback
def async_evaluate_event(hass, event_data):
    """Evaluate events from webhook."""
    event_type = event_data.get(ATTR_EVENT_TYPE)

    if event_type == "person":
        for person in event_data.get(ATTR_PERSONS):
            person_event_data = dict(event_data)
            person_event_data[ATTR_ID] = person.get(ATTR_ID)
            person_event_data[ATTR_NAME] = hass.data[DOMAIN][DATA_PERSONS].get(
                person_event_data[ATTR_ID], DEFAULT_PERSON
            )
            person_event_data[ATTR_IS_KNOWN] = person.get(ATTR_IS_KNOWN)
            person_event_data[ATTR_FACE_URL] = person.get(ATTR_FACE_URL)
            hass.bus.async_fire(
                event_type=NETATMO_EVENT,
                event_data={"type": event_type, "data": person_event_data},
            )
    else:
        hass.bus.async_fire(
            event_type=NETATMO_EVENT,
            event_data={"type": event_type, "data": event_data},
        )
