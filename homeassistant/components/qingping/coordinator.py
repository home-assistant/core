"""Coordinator for Qingping devices connected via MQTT.

The device is push-only: it publishes a TLV encoded packet on
``qingping/<mac>/up`` every few minutes. The coordinator subscribes once
and pushes decoded values to entities via ``async_set_updated_data``.
"""

from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any, override

from qingping_tlv import is_tlv_format, tlv_decode

from homeassistant.components import mqtt
from homeassistant.components.mqtt import async_wait_for_mqtt_client
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import DOMAIN, MQTT_TOPIC_PREFIX, OFFLINE_CHECK_INTERVAL, OFFLINE_TIMEOUT

if TYPE_CHECKING:
    from . import QingpingConfigEntry

_LOGGER = logging.getLogger(__name__)


def _signed_strength(value: int) -> int:
    """Convert an unsigned signal strength to signed dBm."""
    return value - 256 if value >= 128 else value


class QingpingMqttCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for a Qingping device connected via MQTT."""

    config_entry: QingpingConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: QingpingConfigEntry, mac: str
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{mac}",
            update_interval=None,
        )
        self.mac = mac
        self.data = {"online": True, "sensors": {}, "signal_strength": None}
        self._last_message: datetime | None = None

    @override
    async def _async_setup(self) -> None:
        """Wait for MQTT and subscribe to the device topic."""
        if not await async_wait_for_mqtt_client(self.hass):
            raise ConfigEntryNotReady("MQTT integration not available")
        self.config_entry.async_on_unload(
            await mqtt.async_subscribe(
                self.hass,
                f"{MQTT_TOPIC_PREFIX}/{self.mac}/up",
                self._handle_message,
                encoding=None,
            )
        )
        self.config_entry.async_on_unload(
            async_track_time_interval(
                self.hass,
                self._async_check_offline,
                timedelta(seconds=OFFLINE_CHECK_INTERVAL),
            )
        )

    @callback
    def _handle_message(self, message: mqtt.ReceiveMessage) -> None:
        """Update data when a device message arrives."""
        payload = message.payload
        if isinstance(payload, str):
            payload = payload.encode()
        _LOGGER.debug(
            "[%s] Received message on %s: %s",
            self.mac,
            message.topic,
            payload.hex(),
        )
        if not is_tlv_format(payload):
            _LOGGER.debug("[%s] Ignoring payload without TLV marker", self.mac)
            return
        decoded = tlv_decode(payload)
        _LOGGER.debug("[%s] Decoded TLV data: %s", self.mac, decoded)
        sensor_data = decoded.get("sensorData") or []
        if sensor_data:
            # Merge so a packet carrying only part of the values keeps the rest
            sensors = {**self.data["sensors"], **sensor_data[-1]}
        else:
            sensors = self.data["sensors"]
        if (strength := decoded.get("signalStrength")) is not None:
            signal_strength = _signed_strength(strength)
        elif (rssi := sensors.get("rssi")) is not None:
            signal_strength = rssi
        else:
            signal_strength = self.data["signal_strength"]
        self._last_message = dt_util.utcnow()
        self.async_set_updated_data(
            {
                "online": True,
                "sensors": sensors,
                "signal_strength": signal_strength,
            }
        )
        if version := decoded.get("version"):
            self._async_update_sw_version(version)

    @callback
    def _async_check_offline(self, now: datetime) -> None:
        """Mark the device offline if no message arrived within the timeout."""
        if not self.data["online"]:
            return
        if (
            self._last_message is None
            or (now - self._last_message).total_seconds() > OFFLINE_TIMEOUT
        ):
            self.async_set_updated_data({**self.data, "online": False})

    @callback
    def _async_update_sw_version(self, version: str) -> None:
        """Store a firmware version reported by the device."""
        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get_device_by_connection(
            (dr.CONNECTION_NETWORK_MAC, dr.format_mac(self.mac)),
            self.config_entry.entry_id,
        )
        if device is not None and device.sw_version != version:
            device_registry.async_update_device(device.id, sw_version=version)

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Return the current data; the coordinator is push driven."""
        return self.data
