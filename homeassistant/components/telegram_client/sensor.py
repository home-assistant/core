"""Telegram client sensor entities."""

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CLIENT_TYPE_USER,
    CONF_CLIENT_TYPE,
    ICON_ID,
    ICON_LAST_DELETED_MESSAGE_ID,
    ICON_LAST_EDITED_MESSAGE_ID,
    ICON_LAST_SENT_MESSAGE_ID,
    ICON_PHONE,
    ICON_USERNAME,
    SENSOR_FIRST_NAME,
    SENSOR_ID,
    SENSOR_LAST_DELETED_MESSAGE_ID,
    SENSOR_LAST_EDITED_MESSAGE_ID,
    SENSOR_LAST_NAME,
    SENSOR_LAST_SENT_MESSAGE_ID,
    SENSOR_PHONE,
    SENSOR_USERNAME,
    STRING_FIRST_NAME,
    STRING_ID,
    STRING_LAST_DELETED_MESSAGE_ID,
    STRING_LAST_EDITED_MESSAGE_ID,
    STRING_LAST_NAME,
    STRING_LAST_SENT_MESSAGE_ID,
    STRING_PHONE,
    STRING_USERNAME,
)
from .entity import TelegramClientCoordinatorSensor, TelegramClientSensor

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=SENSOR_ID,
        translation_key=SENSOR_ID,
        name=STRING_ID,
        icon=ICON_ID,
    ),
    SensorEntityDescription(
        key=SENSOR_USERNAME,
        translation_key=SENSOR_USERNAME,
        name=STRING_USERNAME,
        icon=ICON_USERNAME,
    ),
    SensorEntityDescription(
        key=SENSOR_LAST_NAME,
        translation_key=SENSOR_LAST_NAME,
        name=STRING_LAST_NAME,
    ),
    SensorEntityDescription(
        key=SENSOR_FIRST_NAME,
        translation_key=SENSOR_FIRST_NAME,
        name=STRING_FIRST_NAME,
    ),
    SensorEntityDescription(
        key=SENSOR_PHONE,
        translation_key=SENSOR_PHONE,
        name=STRING_PHONE,
        icon=ICON_PHONE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Handle Telegram client sensor entries setup."""
    coordinator = entry.runtime_data
    async_add_entities(
        TelegramClientCoordinatorSensor(coordinator, entity_description)
        for entity_description in SENSORS
        if entry.data[CONF_CLIENT_TYPE] == CLIENT_TYPE_USER
        or entity_description.key not in [SENSOR_PHONE, SENSOR_LAST_NAME]
    )
    coordinator.last_sent_message_id = TelegramClientSensor(
        coordinator,
        SensorEntityDescription(
            key=SENSOR_LAST_SENT_MESSAGE_ID,
            translation_key=SENSOR_LAST_SENT_MESSAGE_ID,
            name=STRING_LAST_SENT_MESSAGE_ID,
            icon=ICON_LAST_SENT_MESSAGE_ID,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    )
    coordinator.last_edited_message_id = TelegramClientSensor(
        coordinator,
        SensorEntityDescription(
            key=SENSOR_LAST_EDITED_MESSAGE_ID,
            translation_key=SENSOR_LAST_EDITED_MESSAGE_ID,
            name=STRING_LAST_EDITED_MESSAGE_ID,
            icon=ICON_LAST_EDITED_MESSAGE_ID,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    )
    coordinator.last_deleted_message_id = TelegramClientSensor(
        coordinator,
        SensorEntityDescription(
            key=SENSOR_LAST_DELETED_MESSAGE_ID,
            translation_key=SENSOR_LAST_DELETED_MESSAGE_ID,
            name=STRING_LAST_DELETED_MESSAGE_ID,
            icon=ICON_LAST_DELETED_MESSAGE_ID,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    )
    async_add_entities(
        [
            coordinator.last_sent_message_id,
            coordinator.last_edited_message_id,
            coordinator.last_deleted_message_id,
        ]
    )
