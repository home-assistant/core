"""Flukso binary sensor."""
import logging

from homeassistant.components.mqtt.binary_sensor import MqttBinarySensor

from .const import DOMAIN
from .discovery import get_entities_for_platform

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Add a Flukso binary sensor."""
    _LOGGER.info("Setting up flukso platform binary_sensor")

    configs = get_entities_for_platform(
        "binary_sensor", hass.data[DOMAIN][entry.entry_id]
    )

    async_add_entities(
        [MqttBinarySensor(hass, config, entry, None) for config in configs]
    )
