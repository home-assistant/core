"""Coordinator for Qingping IoT integration."""

import asyncio
import json
import logging
import time
from typing import Any

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import MQTT_TOPIC_PREFIX, OFFLINE_TIMEOUT_REALTIME, TLV_MODELS
from .tlv import is_tlv_format, tlv_decode

_LOGGER = logging.getLogger(__name__)

MQTT_PUBLISH_RETRY_LIMIT = 3
MQTT_PUBLISH_RETRY_DELAY = 5


async def ensure_mqtt_connected(hass: HomeAssistant) -> bool:
    """Ensure MQTT is connected before publishing."""
    for _ in range(5):
        if mqtt.is_connected(hass):
            return True
        await asyncio.sleep(1)
    return False


class QingpingCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for a single Qingping MQTT device."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        mac: str,
        model: str,
        name: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"qingping_{mac}",
            update_interval=None,
        )
        self.config_entry = entry
        self.mac = mac
        self.model = model
        self.name = name

        self._unsub_mqtt: Any = None
        self._pending_setting_publishes: dict[str, asyncio.Task] = {}

        self.data: dict[str, Any] = {
            "online": False,
            "last_timestamp": 0,
            "firmware_version": None,
            "mac": None,
            "battery_charging": None,
            "sensor_data": {},
        }

    @property
    def is_online(self) -> bool:
        """Return whether the device is currently online."""
        return self.data.get("online", False)

    @property
    def is_tlv(self) -> bool:
        """Return whether this device uses the TLV protocol."""
        return self.model in TLV_MODELS

    async def async_start(self) -> None:
        """Start MQTT subscription and periodic tasks."""
        self._unsub_mqtt = await mqtt.async_subscribe(
            self.hass,
            f"{MQTT_TOPIC_PREFIX}/{self.mac}/up",
            self._handle_message,
            1,
            encoding=None,
        )

    async def async_stop(self) -> None:
        """Stop MQTT subscription and periodic tasks."""
        if self._unsub_mqtt:
            self._unsub_mqtt()
            self._unsub_mqtt = None
        for task in self._pending_setting_publishes.values():
            task.cancel()
        self._pending_setting_publishes.clear()

    async def _async_update_data(self) -> dict[str, Any]:
        return self.data

    # -- MQTT message handling --

    @callback
    def _handle_message(self, message: mqtt.ReceiveMessage) -> None:
        """Route incoming MQTT messages."""
        payload: bytes = (
            message.payload.encode()
            if isinstance(message.payload, str)
            else bytes(message.payload)
        )
        try:
            if is_tlv_format(payload):
                self._handle_tlv_message(payload)
            else:
                self._handle_json_message(payload)
        except json.JSONDecodeError:
            _LOGGER.error("[%s] Invalid JSON in MQTT message", self.mac)
        except (ValueError, KeyError, TypeError) as e:
            _LOGGER.error("[%s] Error processing MQTT message: %s", self.mac, e)

    @callback
    def _handle_tlv_message(self, payload: bytes) -> None:
        """Process TLV binary payload."""
        try:
            cmd = payload[2] if len(payload) > 2 else 0
            decoded = tlv_decode(payload)
            _LOGGER.debug("[%s] TLV payload, decoded: %s", self.mac, decoded)
            if not decoded:
                return

            current_timestamp = int(time.time())

            new_data = dict(self.data)
            new_data["last_timestamp"] = current_timestamp

            if "version" in decoded:
                new_data["firmware_version"] = decoded["version"]

            new_data["mac"] = self.mac

            if "batteryCharging" in decoded:
                new_data["battery_charging"] = bool(decoded["batteryCharging"])

            sensor_data_list = decoded.get("sensorData", [])
            if not sensor_data_list:
                self.async_set_updated_data(new_data)
                self._update_online_status(new_data)
                return

            if (
                cmd == 0x42
                and isinstance(sensor_data_list, list)
                and len(sensor_data_list) > 1
            ):
                data = sensor_data_list[-1]
            else:
                data = (
                    sensor_data_list[0]
                    if isinstance(sensor_data_list, list)
                    else sensor_data_list
                )

            new_data["sensor_data"] = data
            new_data["decoded"] = decoded
            self.async_set_updated_data(new_data)
            self._update_online_status(new_data)

        except (ValueError, KeyError, TypeError) as e:
            _LOGGER.error("[%s] Error processing TLV message: %s", self.mac, e)

    @callback
    def _handle_json_message(self, payload: bytes) -> None:
        """Process JSON payload (legacy devices)."""
        payload_dict = json.loads(payload)
        if not isinstance(payload_dict, dict):
            return

        message_type = payload_dict.get("type")
        current_timestamp = int(time.time())

        new_data = dict(self.data)
        new_data["last_timestamp"] = current_timestamp

        version = payload_dict.get("version")
        if version is not None:
            new_data["firmware_version"] = version

        mac_addr = payload_dict.get("mac")
        if mac_addr is not None:
            new_data["mac"] = mac_addr

        # Only process type 17 (history sensor data), skip all others
        if message_type not in (17, "17"):
            self.async_set_updated_data(new_data)
            self._update_online_status(new_data)
            return

        # ACK for type 17 messages that require it
        if payload_dict.get("need_ack") in (1, "1"):
            msg_id = payload_dict.get("id")
            if msg_id is not None:
                self._send_json_ack(msg_id, current_timestamp)

        sensor_data_list = payload_dict.get("sensorData")
        if not isinstance(sensor_data_list, list) or not sensor_data_list:
            self.async_set_updated_data(new_data)
            self._update_online_status(new_data)
            return

        # Extract battery charging state from sensorData
        first_entry = sensor_data_list[0]
        battery_data = first_entry.get("battery")
        if isinstance(battery_data, dict):
            battery_status = battery_data.get("status", 0)
            if battery_status == 2:
                new_data["battery_charging"] = "full"
            else:
                new_data["battery_charging"] = battery_status == 1

        new_data["sensor_data_list"] = sensor_data_list
        self.async_set_updated_data(new_data)
        self._update_online_status(new_data)

    @callback
    def _send_json_ack(self, msg_id: int | str, timestamp: int) -> None:
        """Send ACK (type 18) for received sensor data."""
        ack = json.dumps(
            {
                "type": "18",
                "timestamp": timestamp,
                "ack_id": msg_id,
                "code": 0,
            }
        )
        topic = f"{MQTT_TOPIC_PREFIX}/{self.mac}/down"
        self.hass.async_create_task(
            mqtt.async_publish(self.hass, topic, ack),
            f"qingping_ack_{self.mac}_{msg_id}",
        )
        _LOGGER.debug("[%s] Sent ACK for id=%s", self.mac, msg_id)

    # -- Online status --

    @callback
    def _update_online_status(self, data: dict[str, Any] | None = None) -> None:
        """Determine online/offline based on timeout."""
        data = data or self.data
        last_ts = data.get("last_timestamp", 0)
        timeout = OFFLINE_TIMEOUT_REALTIME

        time_since = int(time.time()) - last_ts
        new_online = time_since <= timeout

        if data.get("online") != new_online:
            new_data = dict(data)
            new_data["online"] = new_online
            old_status = "online" if data.get("online") else "offline"
            new_status = "online" if new_online else "offline"
            _LOGGER.info("[%s] Status: %s -> %s", self.mac, old_status, new_status)

            self.async_set_updated_data(new_data)

    @callback
    def check_online_status(self) -> None:
        """Periodic online status check (called by timer)."""
        self._update_online_status()
