"""The Netatmo integration."""
import logging

from .const import (
    ATTR_CAMERA_ID,
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
    EVENT_ANIMAL,
    EVENT_BUS_ANIMAL,
    EVENT_BUS_HUMAN,
    EVENT_BUS_MOVEMENT,
    EVENT_BUS_OTHER,
    EVENT_BUS_PERSON,
    EVENT_BUS_VEHICLE,
    EVENT_HUMAN,
    EVENT_MOVEMENT,
    EVENT_PERSON,
    EVENT_VEHICLE,
)

_LOGGER = logging.getLogger(__name__)


async def handle_webhook(hass, webhook_id, request):
    """Handle webhook callback."""
    try:
        data = await request.json()
    except ValueError:
        return None

    _LOGGER.error("Got webhook data: %s", data)
    published_data = {
        ATTR_EVENT_TYPE: data.get(ATTR_EVENT_TYPE),
        ATTR_HOME_NAME: data.get(ATTR_HOME_NAME),
        ATTR_CAMERA_ID: data.get(ATTR_CAMERA_ID),
        ATTR_MESSAGE: data.get(ATTR_MESSAGE),
    }
    if data.get(ATTR_EVENT_TYPE) == EVENT_PERSON:
        for person in data[ATTR_PERSONS]:
            published_data[ATTR_ID] = person.get(ATTR_ID)
            published_data[ATTR_NAME] = hass.data[DATA_PERSONS].get(
                published_data[ATTR_ID], DEFAULT_PERSON
            )
            published_data[ATTR_IS_KNOWN] = person.get(ATTR_IS_KNOWN)
            published_data[ATTR_FACE_URL] = person.get(ATTR_FACE_URL)
            hass.bus.async_fire(EVENT_BUS_PERSON, published_data)
    elif data.get(ATTR_EVENT_TYPE) == EVENT_MOVEMENT:
        published_data[ATTR_VIGNETTE_URL] = data.get(ATTR_VIGNETTE_URL)
        published_data[ATTR_SNAPSHOT_URL] = data.get(ATTR_SNAPSHOT_URL)
        hass.bus.async_fire(EVENT_BUS_MOVEMENT, published_data)
    elif data.get(ATTR_EVENT_TYPE) == EVENT_HUMAN:
        published_data[ATTR_VIGNETTE_URL] = data.get(ATTR_VIGNETTE_URL)
        published_data[ATTR_SNAPSHOT_URL] = data.get(ATTR_SNAPSHOT_URL)
        hass.bus.async_fire(EVENT_BUS_HUMAN, published_data)
    elif data.get(ATTR_EVENT_TYPE) == EVENT_ANIMAL:
        published_data[ATTR_VIGNETTE_URL] = data.get(ATTR_VIGNETTE_URL)
        published_data[ATTR_SNAPSHOT_URL] = data.get(ATTR_SNAPSHOT_URL)
        hass.bus.async_fire(EVENT_BUS_ANIMAL, published_data)
    elif data.get(ATTR_EVENT_TYPE) == EVENT_VEHICLE:
        hass.bus.async_fire(EVENT_BUS_VEHICLE, published_data)
        published_data[ATTR_VIGNETTE_URL] = data.get(ATTR_VIGNETTE_URL)
        published_data[ATTR_SNAPSHOT_URL] = data.get(ATTR_SNAPSHOT_URL)
    else:
        hass.bus.async_fire(EVENT_BUS_OTHER, data)
