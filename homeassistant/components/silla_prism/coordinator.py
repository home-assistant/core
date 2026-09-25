"""Coordinator for the Silla Prism integration.

Prism is push-only: it publishes a retained MQTT topic whenever a value
changes. A single subscription to ``<base_topic>/#`` feeds every message into
the :class:`~pysillaprism.PrismDevice`, which accumulates typed state; the
coordinator then pushes updates to entities via ``async_set_updated_data``.

Prism has no last will, so it is considered offline when no message has been
received from it for ``OFFLINE_TIMEOUT``.
"""

from datetime import datetime
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
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_BASE_TOPIC, DOMAIN, OFFLINE_TIMEOUT

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
        self._offline_job = HassJob(self._on_offline, cancel_on_shutdown=True)
        self._cancel_offline: CALLBACK_TYPE | None = None

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
        self._schedule_offline()
        self.config_entry.async_on_unload(self._unschedule_offline)

    @override
    async def _async_update_data(self) -> PrismStatus:
        """Return the accumulated state (populated by retained messages)."""
        return self.device.status

    async def _async_publish(self, topic: str, payload: str) -> None:
        """Publish a command built by the library."""
        await mqtt.async_publish(self.hass, topic, payload)

    @callback
    def _message_received(self, msg: ReceiveMessage) -> None:
        if not isinstance(msg.payload, str):
            return
        was_online = self.last_update_success
        # Only messages the library understands count as a sign of life: the
        # subscription also echoes the commands published by this integration.
        if self.device.handle_message(msg.topic, msg.payload) is None:
            return
        self._schedule_offline()
        if not was_online:
            _LOGGER.info("Prism on %s is back online", self.base_topic)
            self.async_set_updated_data(self.device.status)

    @callback
    def _schedule_offline(self) -> None:
        """(Re)start the countdown after which Prism is considered offline."""
        self._unschedule_offline()
        self._cancel_offline = async_call_later(
            self.hass, OFFLINE_TIMEOUT, self._offline_job
        )

    @callback
    def _unschedule_offline(self) -> None:
        if self._cancel_offline is not None:
            self._cancel_offline()
            self._cancel_offline = None

    @callback
    def _on_offline(self, _now: datetime) -> None:
        self._cancel_offline = None
        self.async_set_update_error(
            UpdateFailed(
                f"No message received from Prism on {self.base_topic} for "
                f"{int(OFFLINE_TIMEOUT.total_seconds())} seconds"
            )
        )

    @callback
    def _on_status_update(self, _update: StatusUpdate) -> None:
        self.async_set_updated_data(self.device.status)

    @callback
    def _on_hello(self, info: HelloInfo) -> None:
        """Enrich the device registry when Prism announces itself."""
        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, self.base_topic), self.config_entry.entry_id
        )
        if device is not None:
            device_registry.async_update_device(
                device.id,
                serial_number=info.serial,
                sw_version=info.sw_version,
            )
