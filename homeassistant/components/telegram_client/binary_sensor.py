"""Telegram client sensor entities."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CLIENT_TYPE_CLIENT,
    CONF_CLIENT_TYPE,
    ICON_PREMIUM,
    SENSOR_PREMIUM,
    SENSOR_RESTRICTED,
    STRING_PREMIUM,
    STRING_RESTRICTED,
)
from .entity import TelegramClientBinarySensor

BINARY_SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key=SENSOR_RESTRICTED,
        translation_key=SENSOR_RESTRICTED,
        name=STRING_RESTRICTED,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    BinarySensorEntityDescription(
        key=SENSOR_PREMIUM,
        translation_key=SENSOR_PREMIUM,
        name=STRING_PREMIUM,
        icon=ICON_PREMIUM,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Telegram client binary sensor entity."""
    coordinator = entry.runtime_data
    binary_sensors = [
        TelegramClientBinarySensor(coordinator, entity_description)
        for entity_description in BINARY_SENSORS
        if entry.data[CONF_CLIENT_TYPE] == CLIENT_TYPE_CLIENT
        or entity_description.key not in [SENSOR_PREMIUM]
    ]
    async_add_entities(binary_sensors)
