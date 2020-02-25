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
    EVENT_BUS_ANIMAL,
    EVENT_BUS_CONNECTION,
    EVENT_BUS_HUMAN,
    EVENT_BUS_HUSH,
    EVENT_BUS_MOVEMENT,
    EVENT_BUS_OFF,
    EVENT_BUS_ON,
    EVENT_BUS_OTHER,
    EVENT_BUS_OUTDOOR,
    EVENT_BUS_PERSON,
    EVENT_BUS_SMOKE,
    EVENT_BUS_TAG_BIG_MOVE,
    EVENT_BUS_TAG_OPEN,
    EVENT_BUS_TAG_SMALL_MOVE,
    EVENT_BUS_TAMPERED,
    EVENT_BUS_VEHICLE,
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
)

_LOGGER = logging.getLogger(__name__)


async def handle_webhook(hass, webhook_id, request):
    """Handle webhook callback."""
    try:
        data = await request.json()
    except ValueError:
        return None

    _LOGGER.debug("Got webhook data: %s", data)

    def evaluate_event(event_data):
        published_data = {
            ATTR_EVENT_TYPE: event_data.get(ATTR_EVENT_TYPE),
            ATTR_HOME_NAME: event_data.get(ATTR_HOME_NAME),
            ATTR_CAMERA_ID: event_data.get(ATTR_CAMERA_ID),
            ATTR_MESSAGE: event_data.get(ATTR_MESSAGE),
        }
        if event_data.get(ATTR_EVENT_TYPE) == EVENT_PERSON:
            for person in event_data[ATTR_PERSONS]:
                published_data[ATTR_ID] = person.get(ATTR_ID)
                published_data[ATTR_NAME] = hass.data[DOMAIN][DATA_PERSONS].get(
                    published_data[ATTR_ID], DEFAULT_PERSON
                )
                published_data[ATTR_IS_KNOWN] = person.get(ATTR_IS_KNOWN)
                published_data[ATTR_FACE_URL] = person.get(ATTR_FACE_URL)
                hass.bus.async_fire(EVENT_BUS_PERSON, published_data)
        elif event_data.get(ATTR_EVENT_TYPE) == EVENT_MOVEMENT:
            published_data[ATTR_VIGNETTE_URL] = event_data.get(ATTR_VIGNETTE_URL)
            published_data[ATTR_SNAPSHOT_URL] = event_data.get(ATTR_SNAPSHOT_URL)
            hass.bus.async_fire(EVENT_BUS_MOVEMENT, published_data)
        elif event_data.get(ATTR_EVENT_TYPE) == EVENT_HUMAN:
            published_data[ATTR_VIGNETTE_URL] = event_data.get(ATTR_VIGNETTE_URL)
            published_data[ATTR_SNAPSHOT_URL] = event_data.get(ATTR_SNAPSHOT_URL)
            hass.bus.async_fire(EVENT_BUS_HUMAN, published_data)
        elif event_data.get(ATTR_EVENT_TYPE) == EVENT_ANIMAL:
            published_data[ATTR_VIGNETTE_URL] = event_data.get(ATTR_VIGNETTE_URL)
            published_data[ATTR_SNAPSHOT_URL] = event_data.get(ATTR_SNAPSHOT_URL)
            hass.bus.async_fire(EVENT_BUS_ANIMAL, published_data)
        elif event_data.get(ATTR_EVENT_TYPE) == EVENT_VEHICLE:
            published_data[ATTR_VIGNETTE_URL] = event_data.get(ATTR_VIGNETTE_URL)
            published_data[ATTR_SNAPSHOT_URL] = event_data.get(ATTR_SNAPSHOT_URL)
            hass.bus.async_fire(EVENT_BUS_VEHICLE, published_data)
        elif event_data.get(ATTR_EVENT_TYPE) == EVENT_CONNECTION:
            hass.bus.async_fire(EVENT_BUS_CONNECTION, published_data)
        elif event_data.get(ATTR_EVENT_TYPE) == EVENT_ON:
            hass.bus.async_fire(EVENT_BUS_ON, published_data)
        elif event_data.get(ATTR_EVENT_TYPE) == EVENT_OFF:
            hass.bus.async_fire(EVENT_BUS_OFF, published_data)
        elif event_data.get(ATTR_EVENT_TYPE) == EVENT_HUSH:
            hass.bus.async_fire(EVENT_BUS_HUSH, published_data)
        elif event_data.get(ATTR_EVENT_TYPE) == EVENT_SMOKE:
            hass.bus.async_fire(EVENT_BUS_SMOKE, published_data)
        elif event_data.get(ATTR_EVENT_TYPE) == EVENT_TAMPERED:
            hass.bus.async_fire(EVENT_BUS_TAMPERED, published_data)
        elif event_data.get(ATTR_EVENT_TYPE) == EVENT_TAG_BIG_MOVE:
            hass.bus.async_fire(EVENT_BUS_TAG_BIG_MOVE, published_data)
        elif event_data.get(ATTR_EVENT_TYPE) == EVENT_TAG_SMALL_MOVE:
            hass.bus.async_fire(EVENT_BUS_TAG_SMALL_MOVE, published_data)
        elif event_data.get(ATTR_EVENT_TYPE) == EVENT_TAG_OPEN:
            hass.bus.async_fire(EVENT_BUS_TAG_OPEN, published_data)
        else:
            hass.bus.async_fire(EVENT_BUS_OTHER, event_data)

    if data.get(ATTR_EVENT_TYPE) == EVENT_OUTDOOR:
        hass.bus.async_fire(EVENT_BUS_OUTDOOR, data)
        for event_data in data.get(ATTR_EVENT_LIST):
            evaluate_event(event_data)
    else:
        evaluate_event(data)
