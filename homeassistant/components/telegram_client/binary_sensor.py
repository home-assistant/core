"""Telegram client sensor entities."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_PREMIUM, CONF_RESTRICTED, CONF_TYPE, CONF_TYPE_CLIENT
from .entity import TelegramClientBinarySensor, TelegramClientBinarySensorDescription

BINARY_SENSORS: tuple[TelegramClientBinarySensorDescription, ...] = (
    TelegramClientBinarySensorDescription(
        key=CONF_RESTRICTED,
        translation_key=CONF_RESTRICTED,
        name="Restricted",
        data_key="me",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    TelegramClientBinarySensorDescription(
        key=CONF_PREMIUM,
        translation_key=CONF_PREMIUM,
        name="Premium",
        data_key="me",
        icon="mdi:star",
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
        if entry.data[CONF_TYPE] == CONF_TYPE_CLIENT
        or entity_description.key not in [CONF_PREMIUM]
    ]
    async_add_entities(binary_sensors)
