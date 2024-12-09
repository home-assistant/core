"""Qbus classes."""

import asyncio
import logging
from typing import Final

from qbusmqttapi.discovery import QbusDiscovery
from qbusmqttapi.factory import QbusMqttTopicFactory

from homeassistant.components.mqtt import async_wait_for_mqtt_client, client as mqtt
from homeassistant.core import HomeAssistant

from .const import DATA_QBUS_CONFIG, DATA_QBUS_CONFIG_EVENT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class QbusConfigContainer:
    """Helper to handle the Qbus config."""

    _WAIT_TIMEOUT: Final[int] = 30
    _topic_factory = QbusMqttTopicFactory()

    @staticmethod
    async def async_get_or_request_config(hass: HomeAssistant) -> QbusDiscovery | None:
        """Get or request Qbus config."""
        hass.data.setdefault(DOMAIN, {})
        domain_data: dict = hass.data[DOMAIN]
        config: QbusDiscovery | None = domain_data.get(DATA_QBUS_CONFIG)

        # Data already available
        if config:
            _LOGGER.debug("Config already available")
            return config

        # Setup event
        _LOGGER.debug("Config missing")
        event: asyncio.Event | None = domain_data.get(DATA_QBUS_CONFIG_EVENT)

        if event is None:
            # Create event
            _LOGGER.debug("Creating config event")
            event = asyncio.Event()
            domain_data[DATA_QBUS_CONFIG_EVENT] = event

        if not await async_wait_for_mqtt_client(hass):
            _LOGGER.debug("MQTT client not ready yet")
            return None

        # Request data
        _LOGGER.debug("Requesting config")
        await mqtt.async_publish(
            hass, QbusConfigContainer._topic_factory.get_get_config_topic(), b""
        )

        # Wait
        try:
            await asyncio.wait_for(event.wait(), QbusConfigContainer._WAIT_TIMEOUT)
        except TimeoutError:
            _LOGGER.debug("Timeout while waiting for config")
            return None

        return domain_data.get(DATA_QBUS_CONFIG)

    @staticmethod
    def store_config(hass: HomeAssistant, config: QbusDiscovery) -> None:
        "Store the Qbus config."
        _LOGGER.debug("Storing config")

        hass.data.setdefault(DOMAIN, {})
        domain_data: dict = hass.data[DOMAIN]
        domain_data[DATA_QBUS_CONFIG] = config

        event: asyncio.Event | None = domain_data.get(DATA_QBUS_CONFIG_EVENT)

        if isinstance(event, asyncio.Event) and not event.is_set():
            _LOGGER.debug("Mark config event as finished")
            event.set()
