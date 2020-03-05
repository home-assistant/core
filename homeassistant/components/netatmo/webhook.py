"""The Netatmo integration."""
import logging

from .const import (
    ATTR_CAMERA_ID,
    ATTR_EVENT_LIST,
    ATTR_EVENT_TYPE,
    ATTR_FACE_URL,
    ATTR_HOME_NAME,
    ATTR_ID,
    ATTR_IS_KNOWN,
    ATTR_MESSAGE,
    ATTR_NAME,
    ATTR_PERSONS,
    ATTR_SNAPSHOT_URL,
    ATTR_VIGNETTE_URL,
    DATA_PERSONS,
    DEFAULT_PERSON,
    DOMAIN,
    EVENT_ANIMAL,
    EVENT_CONNECTION,
    EVENT_HUMAN,
    EVENT_HUSH,
    EVENT_MOVEMENT,
    EVENT_OFF,
    EVENT_ON,
    EVENT_OUTDOOR,
    EVENT_PERSON,
    EVENT_SMOKE,
    EVENT_TAG_BIG_MOVE,
    EVENT_TAG_OPEN,
    EVENT_TAG_SMALL_MOVE,
    EVENT_TAMPERED,
    EVENT_VEHICLE,
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

    if data.get(ATTR_EVENT_TYPE) == EVENT_OUTDOOR:
        hass.bus.async_fire(
            event_type=NETATMO_EVENT, event_data={"type": EVENT_OUTDOOR, "data": data}
        )
        for event_data in data.get(ATTR_EVENT_LIST):
            evaluate_event(hass, event_data)
    else:
        evaluate_event(hass, data)


def evaluate_event(hass, event_data):
    """Evaluate events from webhook."""
    published_data = {
        ATTR_EVENT_TYPE: event_data.get(ATTR_EVENT_TYPE),
        ATTR_HOME_NAME: event_data.get(ATTR_HOME_NAME),
        ATTR_CAMERA_ID: event_data.get(ATTR_CAMERA_ID),
        ATTR_MESSAGE: event_data.get(ATTR_MESSAGE),
    }

    event_type = event_data.get(ATTR_EVENT_TYPE)

    if event_type == EVENT_PERSON:
        for person in event_data.get(ATTR_PERSONS):
            published_data[ATTR_ID] = person.get(ATTR_ID)
            published_data[ATTR_NAME] = hass.data[DOMAIN][DATA_PERSONS].get(
                published_data[ATTR_ID], DEFAULT_PERSON
            )
            published_data[ATTR_IS_KNOWN] = person.get(ATTR_IS_KNOWN)
            published_data[ATTR_FACE_URL] = person.get(ATTR_FACE_URL)
            hass.bus.async_fire(
                event_type=NETATMO_EVENT,
                event_data={"type": event_type, "data": published_data},
            )
    elif event_type in [
        EVENT_MOVEMENT,
        EVENT_HUMAN,
        EVENT_ANIMAL,
        EVENT_VEHICLE,
    ]:
        published_data[ATTR_VIGNETTE_URL] = event_data.get(ATTR_VIGNETTE_URL)
        published_data[ATTR_SNAPSHOT_URL] = event_data.get(ATTR_SNAPSHOT_URL)
        hass.bus.async_fire(
            event_type=NETATMO_EVENT,
            event_data={"type": event_type, "data": published_data},
        )
    elif event_type in [
        EVENT_CONNECTION,
        EVENT_ON,
        EVENT_OFF,
        EVENT_HUSH,
        EVENT_SMOKE,
        EVENT_TAMPERED,
        EVENT_TAG_BIG_MOVE,
        EVENT_TAG_SMALL_MOVE,
        EVENT_TAG_OPEN,
    ]:
        hass.bus.async_fire(
            event_type=NETATMO_EVENT,
            event_data={"type": event_type, "data": published_data},
        )
    else:
        hass.bus.async_fire(
            event_type=NETATMO_EVENT,
            event_data={"type": event_type, "data": event_data},
        )
