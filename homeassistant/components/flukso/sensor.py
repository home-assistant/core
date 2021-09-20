"""Flukso sensor."""
import logging

from homeassistant.components.mqtt.sensor import MqttSensor

from .const import DOMAIN
from .discovery import get_entities_for_platform

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Add a Flukso sensor."""
    _LOGGER.info("Setting up flukso platform sensor")

    configs = get_entities_for_platform("sensor", hass.data[DOMAIN][entry.entry_id])

    async_add_entities([MqttSensor(hass, config, entry, None) for config in configs])
