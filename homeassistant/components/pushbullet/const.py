"""Constants for the pushbullet integration."""

from typing import Final

from homeassistant.components.sensor import SensorEntityDescription

DOMAIN: Final = "pushbullet"
DEFAULT_NAME: Final = "Pushbullet"
DATA_HASS_CONFIG: Final = "pushbullet_hass_config"
DATA_UPDATED: Final = "pushbullet_data_updated"

ATTR_URL: Final = "url"
ATTR_FILE: Final = "file"
ATTR_FILE_URL: Final = "file_url"
ATTR_LIST: Final = "list"

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="application_name",
        name="Application name",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="body",
        name="Body",
    ),
    SensorEntityDescription(
        key="notification_id",
        name="Notification ID",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="notification_tag",
        name="Notification tag",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="package_name",
        name="Package name",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="receiver_email",
        name="Receiver email",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="sender_email",
        name="Sender email",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="source_device_iden",
        name="Sender device ID",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="title",
        name="Title",
    ),
    SensorEntityDescription(
        key="type",
        name="Type",
        entity_registry_enabled_default=False,
    ),
)
