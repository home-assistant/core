"""Flukso binary sensor."""
from homeassistant.components.mqtt.binary_sensor import MqttBinarySensor

from .const import DOMAIN
from .discovery import get_entities_for_platform


async def async_setup_entry(hass, entry, async_add_entities):
    """Add a Flukso binary sensor."""
    configs = get_entities_for_platform(
        "binary_sensor", hass.data[DOMAIN][entry.entry_id]
    )

    async_add_entities(
        [MqttBinarySensor(hass, config, entry, None) for config in configs]
    )
