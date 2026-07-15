"""Coordinator for the Silla Prism integration.

Prism is push-only: it publishes a retained MQTT topic whenever a value
changes. A single subscription to ``<base_topic>/#`` feeds every message into
the :class:`~pysillaprism.PrismDevice`, which accumulates typed state; the
coordinator then pushes updates to entities via ``async_set_updated_data``.
"""

import logging
from typing import override

from pysillaprism import HelloInfo, PrismDevice, PrismStatus
from pysillaprism.parser import StatusUpdate

from homeassistant.components.mqtt import (
    ReceiveMessage,
    async_wait_for_mqtt_client,
    client as mqtt,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_BASE_TOPIC, DOMAIN

_LOGGER = logging.getLogger(__name__)

type PrismConfigEntry = ConfigEntry[PrismCoordinator]


class PrismCoordinator(DataUpdateCoordinator[PrismStatus]):
    """Owns the MQTT subscription and the accumulated Prism state."""

    config_entry: PrismConfigEntry

    def __init__(self, hass: HomeAssistant, entry: PrismConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN)
        self.base_topic: str = entry.data[CONF_BASE_TOPIC]
        self.device = PrismDevice(self.base_topic, publish=self._async_publish)
        self.device.on_status_update = self._on_status_update
        self.device.on_hello = self._on_hello

    async def _async_publish(self, topic: str, payload: str) -> None:
        await mqtt.async_publish(self.hass, topic, payload)

    @override
    async def _async_setup(self) -> None:
        """Wait for MQTT and subscribe to the device's topics once."""
        if not await async_wait_for_mqtt_client(self.hass):
            raise ConfigEntryNotReady("MQTT integration not available")

        self.config_entry.async_on_unload(
            await mqtt.async_subscribe(
                self.hass, self.device.subscription_topic, self._message_received
            )
        )

    @override
    async def _async_update_data(self) -> PrismStatus:
        """Return the accumulated state (populated by retained messages)."""
        return self.device.status

    @callback
    def _message_received(self, msg: ReceiveMessage) -> None:
        if isinstance(msg.payload, str):
            self.device.handle_message(msg.topic, msg.payload)

    @callback
    def _on_status_update(self, _update: StatusUpdate) -> None:
        self.async_set_updated_data(self.device.status)

    @callback
    def _on_hello(self, info: HelloInfo) -> None:
        """Enrich the device registry when Prism announces itself."""
        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, self.base_topic)}
        )
        if device is not None:
            device_registry.async_update_device(
                device.id,
                serial_number=info.serial,
                sw_version=info.sw_version,
            )
