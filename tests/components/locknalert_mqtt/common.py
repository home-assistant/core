"""Common test objects."""

from collections.abc import Iterable
from contextlib import suppress
import copy
import json
import time
from typing import Any
from unittest.mock import ANY, MagicMock, Mock, patch

import paho.mqtt.client as mqtt_client
from paho.mqtt.client import MQTTMessage
import pytest

from homeassistant.components import locknalert_mqtt as mqtt
from homeassistant.components.locknalert_mqtt.const import (
    MQTT_CONNECTION_STATE,
    SUPPORTED_COMPONENTS,
)
from homeassistant.components.locknalert_mqtt.entity import MQTT_ATTRIBUTES_BLOCKED
from homeassistant.components.locknalert_mqtt.models import (
    DATA_MQTT,
    PublishPayloadType,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
    SERVICE_RELOAD,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HassJobType, HomeAssistant, callback
from homeassistant.generated.mqtt import MQTT
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from tests.common import MockConfigEntry
from tests.typing import MqttMockHAClientGenerator, MqttMockPahoClient


@callback
def async_fire_mqtt_message(
    hass: HomeAssistant,
    topic: str,
    payload: bytes | str,
    qos: int = 0,
    retain: bool = False,
    properties: mqtt_client.Properties | None = None,
) -> None:
    """Simulate an incoming MQTT message through the locknalert_mqtt integration.

    Constructs a paho :class:`~paho.mqtt.client.MQTTMessage` and passes it
    directly to the integration's ``_async_mqtt_on_message`` handler, bypassing
    the broker entirely.  String payloads are automatically encoded to UTF-8.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        topic (str): The MQTT topic of the simulated message.
        payload (bytes | str): The message payload.  Strings are encoded to
            UTF-8 bytes automatically.
        qos (int): MQTT quality-of-service level of the simulated message.
        retain (bool): Whether the simulated message should be flagged as
            retained.
        properties (mqtt_client.Properties | None): Optional MQTT v5 properties
            to attach to the message.
    """
    if isinstance(payload, str):
        payload = payload.encode("utf-8")

    msg = MQTTMessage(topic=topic.encode("utf-8"))
    msg.payload = payload
    msg.qos = qos
    msg.retain = retain
    msg.timestamp = time.monotonic()
    msg.properties = properties

    mqtt_data = hass.data[DATA_MQTT]
    assert mqtt_data.client
    mqtt_data.client._async_mqtt_on_message(Mock(), None, msg)


DEFAULT_CONFIG_DEVICE_INFO_ID = {
    "identifiers": ["helloworld"],
    "manufacturer": "Whatever",
    "name": "Beer",
    "model": "Glass",
    "model_id": "XYZ001",
    "hw_version": "rev1",
    "serial_number": "1234deadbeef",
    "sw_version": "0.1-beta",
    "suggested_area": "default_area",
    "configuration_url": "http://example.com",
}

DEFAULT_CONFIG_DEVICE_INFO_MAC = {
    "connections": [[dr.CONNECTION_NETWORK_MAC, "02:5b:26:a8:dc:12"]],
    "manufacturer": "Whatever",
    "name": "Beer",
    "model": "Glass",
    "model_id": "XYZ001",
    "hw_version": "rev1",
    "serial_number": "1234deadbeef",
    "sw_version": "0.1-beta",
    "suggested_area": "default_area",
    "configuration_url": "http://example.com",
}

MOCK_SUBENTRY_ALARM_CONTROL_PANEL_COMPONENT_LOCAL_CODE = {
    "4b06357ef8654e8d9c54cee5bb0e9391": {
        "platform": "alarm_control_panel",
        "name": "Alarm",
        "entity_category": "config",
        "command_topic": "test-topic",
        "state_topic": "test-topic",
        "command_template": "{{action}}",
        "value_template": "{{ value_json.value }}",
        "code": "1234",
        "code_arm_required": True,
        "code_disarm_required": True,
        "code_trigger_required": True,
        "payload_arm_away": "ARM_AWAY",
        "payload_arm_custom_bypass": "ARM_CUSTOM_BYPASS",
        "payload_arm_home": "ARM_HOME",
        "payload_arm_night": "ARM_NIGHT",
        "payload_arm_vacation": "ARM_VACATION",
        "payload_trigger": "TRIGGER",
        "supported_features": ["arm_home", "arm_away", "trigger"],
        "retain": False,
        "entity_picture": "https://example.com/4b06357ef8654e8d9c54cee5bb0e9391",
    },
}
MOCK_SUBENTRY_ALARM_CONTROL_PANEL_COMPONENT_REMOTE_CODE = {
    "4b06357ef8654e8d9c54cee5bb0e9392": {
        "platform": "alarm_control_panel",
        "name": "Alarm",
        "entity_category": None,
        "command_topic": "test-topic",
        "state_topic": "test-topic",
        "command_template": "{{action}}",
        "value_template": "{{ value_json.value }}",
        "code": "REMOTE_CODE",
        "code_arm_required": True,
        "code_disarm_required": True,
        "code_trigger_required": True,
        "payload_arm_away": "ARM_AWAY",
        "payload_arm_custom_bypass": "ARM_CUSTOM_BYPASS",
        "payload_arm_home": "ARM_HOME",
        "payload_arm_night": "ARM_NIGHT",
        "payload_arm_vacation": "ARM_VACATION",
        "payload_trigger": "TRIGGER",
        "supported_features": ["arm_home", "arm_away", "arm_custom_bypass"],
        "retain": False,
        "entity_picture": "https://example.com/4b06357ef8654e8d9c54cee5bb0e9392",
    },
}
MOCK_SUBENTRY_ALARM_CONTROL_PANEL_COMPONENT_REMOTE_CODE_TEXT = {
    "4b06357ef8654e8d9c54cee5bb0e9393": {
        "platform": "alarm_control_panel",
        "name": "Alarm",
        "entity_category": None,
        "command_topic": "test-topic",
        "state_topic": "test-topic",
        "command_template": "{{action}}",
        "value_template": "{{ value_json.value }}",
        "code": "REMOTE_CODE_TEXT",
        "code_arm_required": True,
        "code_disarm_required": True,
        "code_trigger_required": True,
        "payload_arm_away": "ARM_AWAY",
        "payload_arm_custom_bypass": "ARM_CUSTOM_BYPASS",
        "payload_arm_home": "ARM_HOME",
        "payload_arm_night": "ARM_NIGHT",
        "payload_arm_vacation": "ARM_VACATION",
        "payload_trigger": "TRIGGER",
        "supported_features": ["arm_home", "arm_away", "arm_vacation"],
        "retain": False,
        "entity_picture": "https://example.com/4b06357ef8654e8d9c54cee5bb0e9393",
    },
}
MOCK_SUBENTRY_BINARY_SENSOR_COMPONENT = {
    "5b06357ef8654e8d9c54cee5bb0e939b": {
        "platform": "binary_sensor",
        "name": "Hatch",
        "device_class": "door",
        "entity_category": None,
        "state_topic": "test-topic",
        "payload_on": "ON",
        "payload_off": "OFF",
        "expire_after": 1200,
        "off_delay": 5,
        "value_template": "{{ value_json.value }}",
        "entity_picture": "https://example.com/5b06357ef8654e8d9c54cee5bb0e939b",
    },
}
MOCK_SUBENTRY_BUTTON_COMPONENT = {
    "365d05e6607c4dfb8ae915cff71a954b": {
        "platform": "button",
        "name": "Restart",
        "device_class": "restart",
        "command_topic": "test-topic",
        "entity_category": None,
        "payload_press": "PRESS",
        "command_template": "{{ value }}",
        "retain": False,
        "entity_picture": "https://example.com/365d05e6607c4dfb8ae915cff71a954b",
    },
}
MOCK_SUBENTRY_CLIMATE_COMPONENT = {
    "b085c09efba7ec76acd94e2e0f851386": {
        "platform": "climate",
        "name": "Cooler",
        "entity_category": None,
        "entity_picture": "https://example.com/b085c09efba7ec76acd94e2e0f851386",
        "temperature_unit": "C",
        "mode_command_topic": "mode-command-topic",
        "mode_command_template": "{{ value }}",
        "mode_state_topic": "mode-state-topic",
        "mode_state_template": "{{ value_json.mode }}",
        "modes": ["off", "heat", "cool", "auto"],
        # single target temperature
        "temperature_command_topic": "temperature-command-topic",
        "temperature_command_template": "{{ value }}",
        "temperature_state_topic": "temperature-state-topic",
        "temperature_state_template": "{{ value_json.temperature }}",
        "min_temp": 8,
        "max_temp": 28,
        "precision": "0.1",
        "temp_step": 1.0,
        "initial": 19.0,
        # power settings
        "power_command_topic": "power-command-topic",
        "power_command_template": "{{ value }}",
        "payload_on": "ON",
        "payload_off": "OFF",
        # current action settings
        "action_topic": "action-topic",
        "action_template": "{{ value_json.current_action }}",
        # target humidity
        "target_humidity_command_topic": "target-humidity-command-topic",
        "target_humidity_command_template": "{{ value }}",
        "target_humidity_state_topic": "target-humidity-state-topic",
        "target_humidity_state_template": "{{ value_json.target_humidity }}",
        "min_humidity": 20,
        "max_humidity": 80,
        # current temperature
        "current_temperature_topic": "current-temperature-topic",
        "current_temperature_template": "{{ value_json.temperature }}",
        # current humidity
        "current_humidity_topic": "current-humidity-topic",
        "current_humidity_template": "{{ value_json.humidity }}",
        # preset mode
        "preset_mode_command_topic": "preset-mode-command-topic",
        "preset_mode_command_template": "{{ value }}",
        "preset_mode_state_topic": "preset-mode-state-topic",
        "preset_mode_value_template": "{{ value_json.preset_mode }}",
        "preset_modes": ["auto", "eco"],
        # fan mode
        "fan_mode_command_topic": "fan-mode-command-topic",
        "fan_mode_command_template": "{{ value }}",
        "fan_mode_state_topic": "fan-mode-state-topic",
        "fan_mode_state_template": "{{ value_json.fan_mode }}",
        "fan_modes": ["off", "low", "medium", "high"],
        # swing mode
        "swing_mode_command_topic": "swing-mode-command-topic",
        "swing_mode_command_template": "{{ value }}",
        "swing_mode_state_topic": "swing-mode-state-topic",
        "swing_mode_state_template": "{{ value_json.swing_mode }}",
        "swing_modes": ["off", "on"],
        # swing horizontal mode
        "swing_horizontal_mode_command_topic": "swing-horizontal-mode-command-topic",
        "swing_horizontal_mode_command_template": "{{ value }}",
        "swing_horizontal_mode_state_topic": "swing-horizontal-mode-state-topic",
        "swing_horizontal_mode_state_template": "{{ value_json.swing_horizontal_mode }}",
        "swing_horizontal_modes": ["off", "on"],
    },
}
MOCK_SUBENTRY_CLIMATE_HIGH_LOW_COMPONENT = {
    "b085c09efba7ec76acd94e2e0f851387": {
        "platform": "climate",
        "name": "Cooler",
        "entity_category": None,
        "entity_picture": "https://example.com/b085c09efba7ec76acd94e2e0f851387",
        "temperature_unit": "C",
        "mode_command_topic": "mode-command-topic",
        "mode_command_template": "{{ value }}",
        "mode_state_topic": "mode-state-topic",
        "mode_state_template": "{{ value_json.mode }}",
        "modes": ["off", "heat", "cool", "auto"],
        # high/low target temperature
        "temperature_low_command_topic": "temperature-low-command-topic",
        "temperature_low_command_template": "{{ value }}",
        "temperature_low_state_topic": "temperature-low-state-topic",
        "temperature_low_state_template": "{{ value_json.temperature_low }}",
        "temperature_high_command_topic": "temperature-high-command-topic",
        "temperature_high_command_template": "{{ value }}",
        "temperature_high_state_topic": "temperature-high-state-topic",
        "temperature_high_state_template": "{{ value_json.temperature_high }}",
        "min_temp": 8,
        "max_temp": 28,
        "precision": "0.1",
        "temp_step": 1.0,
        "initial": 19.0,
    },
}
MOCK_SUBENTRY_CLIMATE_NO_TARGET_TEMP_COMPONENT = {
    "b085c09efba7ec76acd94e2e0f851388": {
        "platform": "climate",
        "name": "Cooler",
        "entity_category": None,
        "entity_picture": "https://example.com/b085c09efba7ec76acd94e2e0f851388",
        "temperature_unit": "C",
        "mode_command_topic": "mode-command-topic",
        "mode_command_template": "{{ value }}",
        "mode_state_topic": "mode-state-topic",
        "mode_state_template": "{{ value_json.mode }}",
        "modes": ["off", "heat", "cool", "auto"],
    },
}
MOCK_SUBENTRY_COVER_COMPONENT = {
    "b37acf667fa04c688ad7dfb27de2178b": {
        "platform": "cover",
        "name": "Blind",
        "device_class": "blind",
        "entity_category": None,
        "command_topic": "test-topic",
        "payload_stop": None,
        "payload_stop_tilt": "STOP",
        "payload_open": "OPEN",
        "payload_close": "CLOSE",
        "position_closed": 0,
        "position_open": 100,
        "position_template": "{{ value_json.position }}",
        "position_topic": "test-topic/position",
        "set_position_template": "{{ value }}",
        "set_position_topic": "test-topic/position-set",
        "state_closed": "closed",
        "state_closing": "closing",
        "state_open": "open",
        "state_opening": "opening",
        "state_stopped": "stopped",
        "state_topic": "test-topic",
        "tilt_closed_value": 0,
        "tilt_max": 100,
        "tilt_min": 0,
        "tilt_opened_value": 100,
        "tilt_optimistic": False,
        "tilt_command_topic": "test-topic/tilt-set",
        "tilt_command_template": "{{ value }}",
        "tilt_status_topic": "test-topic/tilt",
        "tilt_status_template": "{{ value_json.position }}",
        "retain": False,
        "entity_picture": "https://example.com/b37acf667fa04c688ad7dfb27de2178b",
    },
}
MOCK_SUBENTRY_FAN_COMPONENT = {
    "717f924ae9ca4fe9864d845d75d23c9f": {
        "platform": "fan",
        "name": "Breezer",
        "command_topic": "test-topic",
        "entity_category": None,
        "state_topic": "test-topic",
        "command_template": "{{ value }}",
        "value_template": "{{ value_json.value }}",
        "percentage_command_topic": "test-topic/pct",
        "percentage_state_topic": "test-topic/pct",
        "percentage_command_template": "{{ value }}",
        "percentage_value_template": "{{ value_json.percentage }}",
        "payload_reset_percentage": "None",
        "preset_modes": ["eco", "auto"],
        "preset_mode_command_topic": "test-topic/prm",
        "preset_mode_state_topic": "test-topic/prm",
        "preset_mode_command_template": "{{ value }}",
        "preset_mode_value_template": "{{ value_json.preset_mode }}",
        "payload_reset_preset_mode": "None",
        "oscillation_command_topic": "test-topic/osc",
        "oscillation_state_topic": "test-topic/osc",
        "oscillation_command_template": "{{ value }}",
        "oscillation_value_template": "{{ value_json.oscillation }}",
        "payload_oscillation_off": "oscillate_off",
        "payload_oscillation_on": "oscillate_on",
        "direction_command_topic": "test-topic/dir",
        "direction_state_topic": "test-topic/dir",
        "direction_command_template": "{{ value }}",
        "direction_value_template": "{{ value_json.direction }}",
        "payload_off": "OFF",
        "payload_on": "ON",
        "entity_picture": "https://example.com/717f924ae9ca4fe9864d845d75d23c9f",
        "optimistic": False,
        "retain": False,
        "speed_range_max": 100,
        "speed_range_min": 1,
    },
}
MOCK_SUBENTRY_IMAGE_COMPONENT_DATA = {
    "24402bcbd5b64a54bc32695a5ef752bf": {
        "platform": "image",
        "name": "Merchandise",
        "entity_category": None,
        "image_topic": "test-topic",
        "content_type": "image/jpeg",
        "image_encoding": "b64",
        "entity_picture": "https://example.com/24402bcbd5b64a54bc32695a5ef752bf",
    },
}
MOCK_SUBENTRY_IMAGE_COMPONENT_URL = {
    "326104eb58af48c9ab1f887cded499bb": {
        "platform": "image",
        "name": "Merchandise",
        "entity_category": None,
        "url_topic": "test-topic",
        "url_template": "{{ value_json.value }}",
        "entity_picture": "https://example.com/326104eb58af48c9ab1f887cded499bb",
    },
}
MOCK_SUBENTRY_LIGHT_BASIC_KELVIN_COMPONENT = {
    "8131babc5e8d4f44b82e0761d39091a2": {
        "platform": "light",
        "name": "Basic light",
        "on_command_type": "last",
        "optimistic": True,
        "payload_off": "OFF",
        "payload_on": "ON",
        "command_topic": "test-topic",
        "entity_category": None,
        "schema": "basic",
        "state_topic": "test-topic",
        "color_temp_kelvin": True,
        "state_value_template": "{{ value_json.value }}",
        "brightness_scale": 255,
        "max_kelvin": 6535,
        "min_kelvin": 2000,
        "white_scale": 255,
        "entity_picture": "https://example.com/8131babc5e8d4f44b82e0761d39091a2",
    },
}
MOCK_SUBENTRY_LOCK_COMPONENT = {
    "3faf1318016c46c5aea26707eeb6f100": {
        "platform": "lock",
        "name": "Lock",
        "command_topic": "test-topic",
        "state_topic": "test-topic",
        "command_template": "{{ value }}",
        "value_template": "{{ value_json.value }}",
        "code_format": "^\\d{4}$",
        "payload_open": "OPEN",
        "payload_lock": "LOCK",
        "payload_unlock": "UNLOCK",
        "payload_reset": "None",
        "state_jammed": "JAMMED",
        "state_locked": "LOCKED",
        "state_locking": "LOCKING",
        "state_unlocked": "UNLOCKED",
        "state_unlocking": "UNLOCKING",
        "retain": False,
        "entity_category": None,
        "entity_picture": "https://example.com/3faf1318016c46c5aea26707eeb6f100",
        "optimistic": True,
    },
}
MOCK_SUBENTRY_NOTIFY_COMPONENT1 = {
    "363a7ecad6be4a19b939a016ea93e994": {
        "platform": "notify",
        "name": "Milkman alert",
        "entity_category": None,
        "command_topic": "test-topic",
        "command_template": "{{ value }}",
        "entity_picture": "https://example.com/363a7ecad6be4a19b939a016ea93e994",
        "retain": False,
    },
}
MOCK_SUBENTRY_NOTIFY_COMPONENT2 = {
    "6494827dac294fa0827c54b02459d309": {
        "platform": "notify",
        "name": "The second notifier",
        "entity_category": None,
        "command_topic": "test-topic2",
        "entity_picture": "https://example.com/6494827dac294fa0827c54b02459d309",
    },
}
MOCK_SUBENTRY_NOTIFY_COMPONENT_NO_NAME = {
    "5269352dd9534c908d22812ea5d714cd": {
        "platform": "notify",
        "name": None,
        "entity_category": None,
        "command_topic": "test-topic",
        "command_template": "{{ value }}",
        "entity_picture": "https://example.com/5269352dd9534c908d22812ea5d714cd",
        "retain": False,
    },
}
MOCK_SUBENTRY_NOTIFY_BAD_SCHEMA = {
    "b10b531e15244425a74bb0abb1e9d2c6": {
        "platform": "notify",
        "name": "Test",
        "command_topic": "bad#topic",
    },
}
MOCK_SUBENTRY_NUMBER_COMPONENT_CUSTOM_UNIT = {
    "f9261f6feed443e7b7d5f3fbe2a47413": {
        "platform": "number",
        "name": "Speed",
        "entity_category": None,
        "command_topic": "test-topic",
        "command_template": "{{ value }}",
        "state_topic": "test-topic",
        "min": 0.0,
        "max": 10.0,
        "step": 2.0,
        "mode": "box",
        "unit_of_measurement": "bla",
        "value_template": "{{ value_json.value }}",
        "payload_reset": "None",
        "retain": False,
        "entity_picture": "https://example.com/f9261f6feed443e7b7d5f3fbe2a47413",
    },
}
MOCK_SUBENTRY_NUMBER_COMPONENT_DEVICE_CLASS_UNIT = {
    "f9261f6feed443e7b7d5f3fbe2a47414": {
        "platform": "number",
        "name": "Speed",
        "entity_category": None,
        "command_topic": "test-topic",
        "command_template": "{{ value }}",
        "state_topic": "test-topic",
        "min": 0.0,
        "max": 10.0,
        "step": 2.0,
        "mode": "slider",
        "device_class": "carbon_monoxide",
        "unit_of_measurement": "ppm",
        "value_template": "{{ value_json.value }}",
        "payload_reset": "None",
        "retain": False,
        "entity_picture": "https://example.com/f9261f6feed443e7b7d5f3fbe2a47414",
    },
}
MOCK_SUBENTRY_NUMBER_COMPONENT_NO_UNIT = {
    "f9261f6feed443e7b7d5f3fbe2a47414": {
        "platform": "number",
        "name": "Speed",
        "entity_category": None,
        "command_topic": "test-topic",
        "command_template": "{{ value }}",
        "state_topic": "test-topic",
        "min": 0.0,
        "max": 10.0,
        "step": 2.0,
        "mode": "auto",
        "value_template": "{{ value_json.value }}",
        "payload_reset": "None",
        "retain": False,
        "entity_picture": "https://example.com/f9261f6feed443e7b7d5f3fbe2a47414",
    },
}
MOCK_SUBENTRY_NUMBER_COMPONENT_NONE_UNIT = {
    "a9261f6feed443e7b7d5f3fbe2a47414": {
        "platform": "number",
        "name": "Purifier",
        "entity_category": None,
        "command_topic": "test-topic",
        "command_template": "{{ value }}",
        "state_topic": "test-topic",
        "min": 0.0,
        "max": 10.0,
        "step": 2.0,
        "mode": "auto",
        "device_class": "aqi",
        "unit_of_measurement": "None",
        "value_template": "{{ value_json.value }}",
        "payload_reset": "None",
        "retain": False,
        "entity_picture": "https://example.com/a9261f6feed443e7b7d5f3fbe2a47414",
    },
}
MOCK_SUBENTRY_SELECT_COMPONENT = {
    "fa261f6feed443e7b7d5f3fbe2a47414": {
        "platform": "select",
        "name": "Mode",
        "entity_category": None,
        "command_topic": "test-topic",
        "command_template": "{{ value }}",
        "state_topic": "test-topic",
        "options": ["beer", "milk"],
        "value_template": "{{ value_json.value }}",
        "retain": False,
        "entity_picture": "https://example.com/fa261f6feed443e7b7d5f3fbe2a47414",
    },
}
MOCK_SUBENTRY_SENSOR_COMPONENT = {
    "e9261f6feed443e7b7d5f3fbe2a47412": {
        "platform": "sensor",
        "name": "Energy",
        "entity_category": None,
        "device_class": "enum",
        "state_topic": "test-topic",
        "options": ["low", "medium", "high"],
        "expire_after": 30,
        "value_template": "{{ value_json.value }}",
        "entity_picture": "https://example.com/e9261f6feed443e7b7d5f3fbe2a47412",
    },
}
MOCK_SUBENTRY_SENSOR_COMPONENT_UOM_NULL = {
    "b0f85790a95d4889924602effff06b6e": {
        "platform": "sensor",
        "name": "Air quality",
        "device_class": "aqi",
        "entity_category": None,
        "state_class": "measurement",
        "state_topic": "test-topic",
        # `unit_of_measurement` is stored as a string;
        # it will be filtered from the config when exported or when set up.
        "unit_of_measurement": "None",
        "entity_picture": "https://example.com/b0f85790a95d4889924602effff06b6e",
    },
}
MOCK_SUBENTRY_SENSOR_COMPONENT_STATE_CLASS = {
    "a0f85790a95d4889924602effff06b6e": {
        "platform": "sensor",
        "name": "Energy",
        "entity_category": None,
        "state_class": "measurement",
        "state_topic": "test-topic",
        "entity_picture": "https://example.com/a0f85790a95d4889924602effff06b6e",
    },
}
MOCK_SUBENTRY_SENSOR_COMPONENT_LAST_RESET = {
    "e9261f6feed443e7b7d5f3fbe2a47412": {
        "platform": "sensor",
        "name": "Energy",
        "entity_category": None,
        "state_class": "total",
        "last_reset_value_template": "{{ value_json.value }}",
        "state_topic": "test-topic",
        "entity_picture": "https://example.com/e9261f6feed443e7b7d5f3fbe2a47412",
    },
}
MOCK_SUBENTRY_SIREN_COMPONENT = {
    "3faf1318023c46c5aea26707eeb6f12e": {
        "platform": "siren",
        "name": "Siren",
        "entity_category": None,
        "command_topic": "test-topic",
        "state_topic": "test-topic",
        "command_template": "{{ value }}",
        "command_off_template": "{{ value }}",
        "value_template": "{{ value_json.value }}",
        "payload_off": "OFF",
        "payload_on": "ON",
        "available_tones": ["Happy hour", "Cooling alarm"],
        "support_volume_set": True,
        "support_duration": True,
        "entity_picture": "https://example.com/3faf1318023c46c5aea26707eeb6f12e",
        "optimistic": True,
    },
}
MOCK_SUBENTRY_SWITCH_COMPONENT = {
    "3faf1318016c46c5aea26707eeb6f12e": {
        "platform": "switch",
        "name": "Outlet",
        "entity_category": None,
        "device_class": "outlet",
        "command_topic": "test-topic",
        "state_topic": "test-topic",
        "command_template": "{{ value }}",
        "value_template": "{{ value_json.value }}",
        "payload_off": "OFF",
        "payload_on": "ON",
        "entity_picture": "https://example.com/3faf1318016c46c5aea26707eeb6f12e",
        "optimistic": True,
    },
}
MOCK_SUBENTRY_TEXT_COMPONENT = {
    "09261f6feed443e7b7d5f3fbe2a47413": {
        "platform": "text",
        "name": "MOTD",
        "entity_category": None,
        "command_topic": "test-topic",
        "command_template": "{{ value }}",
        "state_topic": "test-topic",
        "min": 0.0,
        "max": 10.0,
        "mode": "password",
        "pattern": "^[a-z_]*$",
        "value_template": "{{ value_json.value }}",
        "retain": False,
        "entity_picture": "https://example.com/09261f6feed443e7b7d5f3fbe2a47413",
    },
}
MOCK_SUBENTRY_VALVE_COMPONENT_STATE = {
    "09261f6feed443e7b7d5f32345a47413": {
        "platform": "valve",
        "name": "Ice cream",
        "entity_category": None,
        "device_class": None,
        "command_topic": "test-topic",
        "state_topic": "test-topic",
        "command_template": "{{ value }}",
        "value_template": "{{ value_json.value }}",
        "reports_position": False,
        "payload_open": "OPEN",
        "payload_close": "CLOSE",
        "payload_stop": "STOP",
        "state_open": "open",
        "state_opening": "opening",
        "state_closed": "closed",
        "state_closing": "closing",
        "entity_picture": "https://example.com/09261f6feed443e7b7d5f32345a47413",
        "retain": True,
        "optimistic": True,
    },
}
MOCK_SUBENTRY_VALVE_COMPONENT_POSITION = {
    "09261f6feed443e7b7d5f32345a47414": {
        "platform": "valve",
        "name": "Ice cream",
        "entity_category": None,
        "device_class": "water",
        "command_topic": "test-topic",
        "state_topic": "test-topic",
        "command_template": "{{ value }}",
        "value_template": "{{ value_json.value }}",
        "reports_position": True,
        "position_closed": 0,
        "position_open": 100,
        "payload_stop": "STOP",
        "state_opening": "opening",
        "state_closing": "closing",
        "entity_picture": "https://example.com/09261f6feed443e7b7d5f32345a47414",
        "retain": True,
        "optimistic": False,
    },
}
MOCK_SUBENTRY_WATER_HEATER_COMPONENT = {
    "b085c09efba7ec76acd94e2e0f851123": {
        "platform": "water_heater",
        "name": "Boyler",
        "entity_category": None,
        "entity_picture": "https://example.com/b085c09efba7ec76acd94e2e0f851123",
        "temperature_unit": "C",
        "mode_command_topic": "mode-command-topic",
        "mode_command_template": "{{ value }}",
        "mode_state_topic": "mode-state-topic",
        "mode_state_template": "{{ value_json.mode }}",
        "modes": ["off", "gas", "electric"],
        # target temperature
        "temperature_command_topic": "temperature-command-topic",
        "temperature_command_template": "{{ value }}",
        "temperature_state_topic": "temperature-state-topic",
        "temperature_state_template": "{{ value_json.temperature }}",
        "min_temp": 43,
        "max_temp": 60,
        "precision": "0.1",
        "initial": 43,
        # power settings
        "power_command_topic": "power-command-topic",
        "power_command_template": "{{ value }}",
        "payload_on": "ON",
        "payload_off": "OFF",
        # current temperature
        "current_temperature_topic": "current-temperature-topic",
        "current_temperature_template": "{{ value_json.temperature }}",
    },
}

MOCK_SUBENTRY_AVAILABILITY_DATA = {
    "availability": {
        "availability_topic": "test/availability",
        "availability_template": "{{ value_json.availability }}",
        "payload_available": "online",
        "payload_not_available": "offline",
    }
}

MOCK_SUBENTRY_DEVICE_DATA = {
    "name": "Milk notifier",
    "sw_version": "1.0",
    "hw_version": "2.1 rev a",
    "model": "Model XL",
    "model_id": "mn002",
    "manufacturer": "Milk Masters",
    "configuration_url": "https://example.com",
}

MOCK_NOTIFY_SUBENTRY_DATA_MULTI = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 0}},
    "components": MOCK_SUBENTRY_NOTIFY_COMPONENT1 | MOCK_SUBENTRY_NOTIFY_COMPONENT2,
} | MOCK_SUBENTRY_AVAILABILITY_DATA

MOCK_ALARM_CONTROL_PANEL_LOCAL_CODE_SUBENTRY_DATA = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 0}},
    "components": MOCK_SUBENTRY_ALARM_CONTROL_PANEL_COMPONENT_LOCAL_CODE,
}
MOCK_ALARM_CONTROL_PANEL_REMOTE_CODE_TEXT_SUBENTRY_DATA = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 1}},
    "components": MOCK_SUBENTRY_ALARM_CONTROL_PANEL_COMPONENT_REMOTE_CODE_TEXT,
}
MOCK_ALARM_CONTROL_PANEL_REMOTE_CODE_SUBENTRY_DATA = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 1}},
    "components": MOCK_SUBENTRY_ALARM_CONTROL_PANEL_COMPONENT_REMOTE_CODE,
}
MOCK_BINARY_SENSOR_SUBENTRY_DATA = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 2}},
    "components": MOCK_SUBENTRY_BINARY_SENSOR_COMPONENT,
}
MOCK_BUTTON_SUBENTRY_DATA = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 2}},
    "components": MOCK_SUBENTRY_BUTTON_COMPONENT,
}
MOCK_CLIMATE_SUBENTRY_DATA = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 0}},
    "components": MOCK_SUBENTRY_CLIMATE_COMPONENT,
}
MOCK_CLIMATE_HIGH_LOW_SUBENTRY_DATA = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 1}},
    "components": MOCK_SUBENTRY_CLIMATE_HIGH_LOW_COMPONENT,
}
MOCK_CLIMATE_NO_TARGET_TEMP_SUBENTRY_DATA = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 2}},
    "components": MOCK_SUBENTRY_CLIMATE_NO_TARGET_TEMP_COMPONENT,
}
MOCK_COVER_SUBENTRY_DATA = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 0}},
    "components": MOCK_SUBENTRY_COVER_COMPONENT,
}
MOCK_FAN_SUBENTRY_DATA = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 0}},
    "components": MOCK_SUBENTRY_FAN_COMPONENT,
}
MOCK_IMAGE_SUBENTRY_DATA_IMAGE_DATA = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 0}},
    "components": MOCK_SUBENTRY_IMAGE_COMPONENT_DATA,
}
MOCK_IMAGE_SUBENTRY_DATA_IMAGE_URL = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 0}},
    "components": MOCK_SUBENTRY_IMAGE_COMPONENT_URL,
}
MOCK_LIGHT_BASIC_KELVIN_SUBENTRY_DATA = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 0}},
    "components": MOCK_SUBENTRY_LIGHT_BASIC_KELVIN_COMPONENT,
}
MOCK_LOCK_SUBENTRY_DATA = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 0}},
    "components": MOCK_SUBENTRY_LOCK_COMPONENT,
}
MOCK_NOTIFY_SUBENTRY_DATA = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 1}},
    "components": MOCK_SUBENTRY_NOTIFY_COMPONENT1,
}
MOCK_NOTIFY_SUBENTRY_DATA_NO_NAME = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 0}},
    "components": MOCK_SUBENTRY_NOTIFY_COMPONENT_NO_NAME,
}
MOCK_NUMBER_SUBENTRY_DATA_CUSTOM_UNIT = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 0}},
    "components": MOCK_SUBENTRY_NUMBER_COMPONENT_CUSTOM_UNIT,
}
MOCK_NUMBER_SUBENTRY_DATA_DEVICE_CLASS_UNIT = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 0}},
    "components": MOCK_SUBENTRY_NUMBER_COMPONENT_DEVICE_CLASS_UNIT,
}
MOCK_NUMBER_SUBENTRY_DATA_NO_UNIT = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 0}},
    "components": MOCK_SUBENTRY_NUMBER_COMPONENT_NO_UNIT,
}
MOCK_NUMBER_SUBENTRY_DATA_NONE_UNIT = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 0}},
    "components": MOCK_SUBENTRY_NUMBER_COMPONENT_NONE_UNIT,
}
MOCK_SELECT_SUBENTRY_DATA = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 0}},
    "components": MOCK_SUBENTRY_SELECT_COMPONENT,
}
MOCK_SENSOR_SUBENTRY_DATA = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 0}},
    "components": MOCK_SUBENTRY_SENSOR_COMPONENT,
}
MOCK_SENSOR_SUBENTRY_DATA_STATE_CLASS = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 0}},
    "components": MOCK_SUBENTRY_SENSOR_COMPONENT_STATE_CLASS,
}
MOCK_SENSOR_SUBENTRY_DATA_UOM_NONE = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 0}},
    "components": MOCK_SUBENTRY_SENSOR_COMPONENT_UOM_NULL,
}
MOCK_SENSOR_SUBENTRY_DATA_LAST_RESET_TEMPLATE = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 0}},
    "components": MOCK_SUBENTRY_SENSOR_COMPONENT_LAST_RESET,
}
MOCK_SIREN_SUBENTRY_DATA = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 0}},
    "components": MOCK_SUBENTRY_SIREN_COMPONENT,
}
MOCK_SWITCH_SUBENTRY_DATA = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 0}},
    "components": MOCK_SUBENTRY_SWITCH_COMPONENT,
}
MOCK_TEXT_SUBENTRY_DATA = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 0}},
    "components": MOCK_SUBENTRY_TEXT_COMPONENT,
}
MOCK_VALVE_SUBENTRY_DATA_STATE = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 0}},
    "components": MOCK_SUBENTRY_VALVE_COMPONENT_STATE,
}
MOCK_VALVE_SUBENTRY_DATA_POSITION = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 2}},
    "components": MOCK_SUBENTRY_VALVE_COMPONENT_POSITION,
}
MOCK_WATER_HEATER_SUBENTRY_DATA = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 0}},
    "components": MOCK_SUBENTRY_WATER_HEATER_COMPONENT,
}
MOCK_SUBENTRY_DATA_BAD_COMPONENT_SCHEMA = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 0}},
    "components": MOCK_SUBENTRY_NOTIFY_BAD_SCHEMA,
}
MOCK_SUBENTRY_DATA_SET_MIX = {
    "device": MOCK_SUBENTRY_DEVICE_DATA | {"mqtt_settings": {"qos": 0}},
    "components": MOCK_SUBENTRY_NOTIFY_COMPONENT1
    | MOCK_SUBENTRY_NOTIFY_COMPONENT2
    | MOCK_SUBENTRY_LIGHT_BASIC_KELVIN_COMPONENT
    | MOCK_SUBENTRY_SWITCH_COMPONENT
    | MOCK_SUBENTRY_SENSOR_COMPONENT_UOM_NULL,
} | MOCK_SUBENTRY_AVAILABILITY_DATA
_SENTINEL = object()

DISCOVERY_COUNT = sum(len(discovery_topic) for discovery_topic in MQTT.values())
DEVICE_DISCOVERY_COUNT = 2

type _MqttMessageType = list[tuple[str, str]]
type _AttributesType = list[tuple[str, Any]]
type _StateDataType = (
    list[tuple[_MqttMessageType, str, _AttributesType | None]]
    | list[tuple[_MqttMessageType, str, None]]
)


def help_all_subscribe_calls(mqtt_client_mock: MqttMockPahoClient) -> list[Any]:
    """Flatten all recorded paho subscribe call arguments into a single list.

    Handles both single-topic and batch-topic paho subscribe calls.

    Args:
        mqtt_client_mock (MqttMockPahoClient): The mock paho client whose
            ``subscribe.mock_calls`` are inspected.

    Returns:
        list[Any]: All subscribe call argument tuples, flattened one level.
    """
    all_calls = []
    for call_l1 in mqtt_client_mock.subscribe.mock_calls:
        if isinstance(call_l1[1][0], list):
            for call_l2 in call_l1[1]:
                all_calls.extend(call_l2)
        else:
            all_calls.append(call_l1[1])
    return all_calls


def help_custom_config(
    mqtt_entity_domain: str,
    mqtt_base_config: ConfigType,
    mqtt_entity_configs: Iterable[ConfigType],
) -> ConfigType:
    """Build a parametrised MQTT config from a base config plus per-entity overrides.

    Deep-copies *mqtt_base_config* and replaces the entity list under
    ``locknalert_mqtt.<mqtt_entity_domain>`` with one entry per item in
    *mqtt_entity_configs*, each merged on top of the base entity config.

    Args:
        mqtt_entity_domain (str): The HA platform domain, e.g.
            ``"alarm_control_panel"``.
        mqtt_base_config (ConfigType): The base ``{locknalert_mqtt: {domain: {...}}}``
            config dict to start from.
        mqtt_entity_configs (Iterable[ConfigType]): Dicts of overrides; one
            entity instance is generated per item.

    Returns:
        ConfigType: A new config dict with the entity list replaced by the
            generated instances.
    """
    config: ConfigType = copy.deepcopy(mqtt_base_config)
    entity_instances: list[ConfigType] = []
    for instance in mqtt_entity_configs:
        base: ConfigType = copy.deepcopy(
            mqtt_base_config[mqtt.DOMAIN][mqtt_entity_domain]
        )
        base.update(instance)
        entity_instances.append(base)
    config[mqtt.DOMAIN][mqtt_entity_domain] = entity_instances
    return config


async def help_test_availability_when_connection_lost(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator, domain: str
) -> None:
    """Verify a platform entity becomes unavailable when the MQTT connection drops.

    Simulates a disconnection by setting ``mqtt_mock.connected = False`` and
    dispatching :data:`~.const.MQTT_CONNECTION_STATE`.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        mqtt_mock_entry (MqttMockHAClientGenerator): Entry setup generator for
            the locknalert_mqtt config entry.
        domain (str): HA platform domain under test (e.g. ``"alarm_control_panel"``).
    """
    mqtt_mock = await mqtt_mock_entry()
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.test")
    assert state and state.state != STATE_UNAVAILABLE

    mqtt_mock.connected = False
    async_dispatcher_send(hass, MQTT_CONNECTION_STATE, False)
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.test")
    assert state and state.state == STATE_UNAVAILABLE


async def help_test_availability_without_topic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
) -> None:
    """Verify a platform entity is available when no availability topic is configured.

    Asserts that ``availability_topic`` is absent from *config* and that the
    entity state is not ``STATE_UNAVAILABLE`` after setup.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        mqtt_mock_entry (MqttMockHAClientGenerator): Entry setup generator.
        domain (str): HA platform domain under test.
        config (ConfigType): Entity config dict that must not contain
            ``availability_topic``.
    """
    assert "availability_topic" not in config[mqtt.DOMAIN][domain]
    await mqtt_mock_entry()
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.test")
    assert state and state.state != STATE_UNAVAILABLE


async def help_test_default_availability_payload(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
    no_assumed_state: bool = False,
    state_topic: str | None = None,
    state_message: str | None = None,
) -> None:
    """Verify availability tracking with the default ``online`` / ``offline`` payloads.

    Injects ``availability_topic`` into *config*, sets up the entry, then
    fires ``"online"`` and ``"offline"`` messages and asserts entity state
    changes.  Optionally verifies that a state message received while offline
    does not make the entity available until an ``"online"`` payload arrives.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        mqtt_mock_entry (MqttMockHAClientGenerator): Entry setup generator.
        domain (str): HA platform domain under test.
        config (ConfigType): Base entity config dict.
        no_assumed_state (bool): When ``True``, also asserts that the entity
            does not have ``assumed_state`` after becoming available.
        state_topic (str | None): Optional extra topic to fire a state message
            on while the entity is offline, to confirm it stays offline.
        state_message (str | None): Payload for *state_topic*.
    """
    # Add availability settings to config
    config = copy.deepcopy(config)
    config[mqtt.DOMAIN][domain]["availability_topic"] = "availability-topic"

    with patch("homeassistant.config.load_yaml_config_file", return_value=config):
        await mqtt_mock_entry()

    state = hass.states.get(f"{domain}.test")
    assert state and state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic", "online")

    state = hass.states.get(f"{domain}.test")
    assert state and state.state != STATE_UNAVAILABLE
    if no_assumed_state:
        assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "availability-topic", "offline")

    state = hass.states.get(f"{domain}.test")
    assert state and state.state == STATE_UNAVAILABLE

    if state_topic is not None and state_message is not None:
        async_fire_mqtt_message(hass, state_topic, state_message)

        state = hass.states.get(f"{domain}.test")
        assert state and state.state == STATE_UNAVAILABLE

        async_fire_mqtt_message(hass, "availability-topic", "online")

        state = hass.states.get(f"{domain}.test")
        assert state and state.state != STATE_UNAVAILABLE


async def help_test_custom_availability_payload(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
    no_assumed_state: bool = False,
    state_topic: str | None = None,
    state_message: str | None = None,
) -> None:
    """Verify availability tracking with custom ``good`` / ``nogood`` payloads.

    Injects ``availability_topic``, ``payload_available = "good"``, and
    ``payload_not_available = "nogood"`` into *config*, then asserts entity
    state changes in the same way as
    :func:`help_test_default_availability_payload`.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        mqtt_mock_entry (MqttMockHAClientGenerator): Entry setup generator.
        domain (str): HA platform domain under test.
        config (ConfigType): Base entity config dict.
        no_assumed_state (bool): When ``True``, also asserts no
            ``assumed_state`` after becoming available.
        state_topic (str | None): Optional topic to fire while offline.
        state_message (str | None): Payload for *state_topic*.
    """
    # Add availability settings to config
    config = copy.deepcopy(config)
    config[mqtt.DOMAIN][domain]["availability_topic"] = "availability-topic"
    config[mqtt.DOMAIN][domain]["payload_available"] = "good"
    config[mqtt.DOMAIN][domain]["payload_not_available"] = "nogood"
    with patch("homeassistant.config.load_yaml_config_file", return_value=config):
        await mqtt_mock_entry()

    state = hass.states.get(f"{domain}.test")
    assert state and state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic", "good")

    state = hass.states.get(f"{domain}.test")
    assert state and state.state != STATE_UNAVAILABLE
    if no_assumed_state:
        assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "availability-topic", "nogood")

    state = hass.states.get(f"{domain}.test")
    assert state and state.state == STATE_UNAVAILABLE

    if state_topic is not None and state_message is not None:
        async_fire_mqtt_message(hass, state_topic, state_message)

        state = hass.states.get(f"{domain}.test")
        assert state and state.state == STATE_UNAVAILABLE

        async_fire_mqtt_message(hass, "availability-topic", "good")

        state = hass.states.get(f"{domain}.test")
        assert state and state.state != STATE_UNAVAILABLE


async def help_test_setting_attribute_via_mqtt_json_message(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
) -> None:
    """Verify JSON-formatted MQTT payloads populate entity attributes.

    Injects ``json_attributes_topic = "attr-topic"`` into *config*, fires a
    JSON payload ``{"val": "100"}`` and asserts the ``val`` attribute is set.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        mqtt_mock_entry (MqttMockHAClientGenerator): Entry setup generator.
        domain (str): HA platform domain under test.
        config (ConfigType): Base entity config dict.
    """
    # Add JSON attributes settings to config
    config = copy.deepcopy(config)
    config[mqtt.DOMAIN][domain]["json_attributes_topic"] = "attr-topic"
    with patch("homeassistant.config.load_yaml_config_file", return_value=config):
        await mqtt_mock_entry()

    async_fire_mqtt_message(hass, "attr-topic", '{ "val": "100" }')
    state = hass.states.get(f"{domain}.test")

    assert state and state.attributes.get("val") == "100"


async def help_test_setting_blocked_attribute_via_mqtt_json_message(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
    extra_blocked_attributes: frozenset[str] | None,
) -> None:
    """Verify that blocked entity attributes cannot be overwritten via MQTT JSON.

    Fires JSON payloads targeting every attribute in
    :data:`~.entity.MQTT_ATTRIBUTES_BLOCKED` and in *extra_blocked_attributes*
    and asserts none of them are reflected on the entity state.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        mqtt_mock_entry (MqttMockHAClientGenerator): Entry setup generator.
        domain (str): HA platform domain under test.
        config (ConfigType): Base entity config dict used for discovery setup.
        extra_blocked_attributes (frozenset[str] | None): Additional platform-
            specific attributes that should also be blocked, or ``None``.
    """
    await mqtt_mock_entry()
    extra_blocked_attribute_list = list(extra_blocked_attributes or [])

    # Add JSON attributes settings to config
    config = copy.deepcopy(config)
    config[mqtt.DOMAIN][domain]["json_attributes_topic"] = "attr-topic"
    data = json.dumps(config[mqtt.DOMAIN][domain])
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()
    val = "abc123"

    for attr in MQTT_ATTRIBUTES_BLOCKED:
        async_fire_mqtt_message(hass, "attr-topic", json.dumps({attr: val}))
        state = hass.states.get(f"{domain}.test")
        assert state and state.attributes.get(attr) != val

    for attr in extra_blocked_attribute_list:
        async_fire_mqtt_message(hass, "attr-topic", json.dumps({attr: val}))
        state = hass.states.get(f"{domain}.test")
        assert state and state.attributes.get(attr) != val


async def help_test_setting_attribute_with_template(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
) -> None:
    """Verify that a ``json_attributes_template`` transforms the JSON payload before extracting attributes.

    Injects ``json_attributes_topic`` and a template that selects the ``Timer1``
    sub-object, fires a nested JSON payload, and asserts that the ``Arm`` and
    ``Time`` attributes are correctly extracted from the sub-object.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        mqtt_mock_entry (MqttMockHAClientGenerator): Entry setup generator.
        domain (str): HA platform domain under test.
        config (ConfigType): Base entity config dict.
    """
    # Add JSON attributes settings to config
    config = copy.deepcopy(config)
    config[mqtt.DOMAIN][domain]["json_attributes_topic"] = "attr-topic"
    config[mqtt.DOMAIN][domain]["json_attributes_template"] = (
        "{{ value_json['Timer1'] | tojson }}"
    )
    with patch("homeassistant.config.load_yaml_config_file", return_value=config):
        await mqtt_mock_entry()

    async_fire_mqtt_message(
        hass, "attr-topic", json.dumps({"Timer1": {"Arm": 0, "Time": "22:18"}})
    )
    state = hass.states.get(f"{domain}.test")

    assert state is not None
    assert state.attributes.get("Arm") == 0
    assert state.attributes.get("Time") == "22:18"


async def help_test_update_with_json_attrs_not_dict(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    domain: str,
    config: ConfigType,
) -> None:
    """Verify that a non-dict JSON payload is rejected and logged as an error.

    Fires a JSON array payload on the attributes topic and asserts the ``val``
    attribute is not set and that ``"JSON result was not a dictionary"`` appears
    in the log.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        mqtt_mock_entry (MqttMockHAClientGenerator): Entry setup generator.
        caplog (pytest.LogCaptureFixture): Log capture fixture for assertion.
        domain (str): HA platform domain under test.
        config (ConfigType): Base entity config dict.
    """
    # Add JSON attributes settings to config
    config = copy.deepcopy(config)
    config[mqtt.DOMAIN][domain]["json_attributes_topic"] = "attr-topic"
    with patch("homeassistant.config.load_yaml_config_file", return_value=config):
        await mqtt_mock_entry()

    async_fire_mqtt_message(hass, "attr-topic", '[ "list", "of", "things"]')
    state = hass.states.get(f"{domain}.test")

    assert state and state.attributes.get("val") is None
    assert "JSON result was not a dictionary" in caplog.text


async def help_test_update_with_json_attrs_bad_json(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    domain: str,
    config: ConfigType,
) -> None:
    """Verify that a malformed JSON attributes payload is rejected and logged as an error.

    Fires an invalid JSON string on the attributes topic and asserts that the
    ``val`` attribute is absent and that ``"Erroneous JSON"`` appears in the
    log.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        mqtt_mock_entry (MqttMockHAClientGenerator): Entry setup generator.
        caplog (pytest.LogCaptureFixture): Log capture fixture for assertion.
        domain (str): HA platform domain under test.
        config (ConfigType): Base entity config dict.
    """
    # Add JSON attributes settings to config
    config = copy.deepcopy(config)
    config[mqtt.DOMAIN][domain]["json_attributes_topic"] = "attr-topic"
    with patch("homeassistant.config.load_yaml_config_file", return_value=config):
        await mqtt_mock_entry()

    async_fire_mqtt_message(hass, "attr-topic", "This is not JSON")

    state = hass.states.get(f"{domain}.test")
    assert state and state.attributes.get("val") is None
    assert "Erroneous JSON: This is not JSON" in caplog.text


async def help_test_discovery_update_attr(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
) -> None:
    """Verify that the attributes topic subscription updates correctly after a discovery re-config.

    Sets up with ``json_attributes_topic = "attr-topic1"``, publishes a
    value, then re-discovers with ``"attr-topic2"`` and verifies the old
    subscription is cancelled and the new one is active.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        mqtt_mock_entry (MqttMockHAClientGenerator): Entry setup generator.
        domain (str): HA platform domain under test.
        config (ConfigType): Base entity config dict.
    """
    await mqtt_mock_entry()
    # Add JSON attributes settings to config
    config1 = copy.deepcopy(config)
    config1[mqtt.DOMAIN][domain]["json_attributes_topic"] = "attr-topic1"
    config2 = copy.deepcopy(config)
    config2[mqtt.DOMAIN][domain]["json_attributes_topic"] = "attr-topic2"
    data1 = json.dumps(config1[mqtt.DOMAIN][domain])
    data2 = json.dumps(config2[mqtt.DOMAIN][domain])

    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data1)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "attr-topic1", '{ "val": "100" }')
    state = hass.states.get(f"{domain}.test")
    assert state and state.attributes.get("val") == "100"

    # Change json_attributes_topic
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data2)
    await hass.async_block_till_done()

    # Verify we are no longer subscribing to the old topic
    async_fire_mqtt_message(hass, "attr-topic1", '{ "val": "50" }')
    state = hass.states.get(f"{domain}.test")
    assert state and state.attributes.get("val") != "50"

    # Verify we are subscribing to the new topic
    async_fire_mqtt_message(hass, "attr-topic2", '{ "val": "75" }')
    state = hass.states.get(f"{domain}.test")
    assert state and state.attributes.get("val") == "75"


async def help_test_unique_id(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator, domain: str
) -> None:
    """Verify that duplicate unique_ids result in only one entity being created.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        mqtt_mock_entry (MqttMockHAClientGenerator): Entry setup generator
            that must have been configured with duplicate unique_ids.
        domain (str): HA platform domain under test.
    """
    await mqtt_mock_entry()
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(domain)) == 1


async def help_test_discovery_removal(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    data: str,
) -> None:
    """Verify that an entity is removed when an empty discovery payload is received.

    Fires *data* on the discovery topic to create the entity, then fires an
    empty string to remove it, and asserts the entity state is gone.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        mqtt_mock_entry (MqttMockHAClientGenerator): Entry setup generator.
        domain (str): HA platform domain under test.
        data (str): JSON discovery payload string for the entity to create.
    """
    await mqtt_mock_entry()
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.test")
    assert state is not None
    assert state.name == "test"

    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", "")
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.test")
    assert state is None


async def help_test_discovery_update(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    discovery_config1: DiscoveryInfoType,
    discovery_config2: DiscoveryInfoType,
    state_data1: _StateDataType | None = None,
    state_data2: _StateDataType | None = None,
) -> None:
    """Verify entity config is updated correctly when a new discovery payload arrives.

    Fires *discovery_config1* (with extra unknown keys to test forward-compat),
    optionally fires *state_data1* messages and asserts their effects, then
    fires *discovery_config2* and asserts the entity is updated (renamed to
    ``"Milk"``).

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        mqtt_mock_entry (MqttMockHAClientGenerator): Entry setup generator.
        domain (str): HA platform domain under test.
        discovery_config1 (DiscoveryInfoType): First discovery payload dict
            (entity named ``"Beer"``).
        discovery_config2 (DiscoveryInfoType): Second discovery payload dict
            (entity named ``"Milk"``).
        state_data1 (_StateDataType | None): Optional MQTT messages to fire
            and assert after the first discovery, or ``None``.
        state_data2 (_StateDataType | None): Optional MQTT messages to fire
            and assert after the second discovery, or ``None``.
    """
    await mqtt_mock_entry()
    # Add some future configuration to the configurations
    config1 = copy.deepcopy(discovery_config1)
    config1["some_future_option_1"] = "future_option_1"
    config2 = copy.deepcopy(discovery_config2)
    config2["some_future_option_2"] = "future_option_2"
    discovery_data1 = json.dumps(config1)
    discovery_data2 = json.dumps(config2)

    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", discovery_data1)
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.beer")
    assert state is not None
    assert state.name == "Beer"

    if state_data1:
        for mqtt_messages, expected_state, attributes in state_data1:
            for topic, data in mqtt_messages:
                async_fire_mqtt_message(hass, topic, data)
            state = hass.states.get(f"{domain}.beer")
            assert state is not None
            if expected_state:
                assert state.state == expected_state
            if attributes:
                for attr, value in attributes:
                    assert state.attributes.get(attr) == value

    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", discovery_data2)
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.beer")
    assert state is not None
    assert state.name == "Milk"

    if state_data2:
        for mqtt_messages, expected_state, attributes in state_data2:
            for topic, data in mqtt_messages:
                async_fire_mqtt_message(hass, topic, data)
            state = hass.states.get(f"{domain}.beer")
            assert state is not None
            if expected_state:
                assert state.state == expected_state
            if attributes:
                for attr, value in attributes:
                    assert state.attributes.get(attr) == value

    state = hass.states.get(f"{domain}.milk")
    assert state is None


async def help_test_discovery_update_unchanged(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    data1: str,
    discovery_update: MagicMock,
) -> None:
    """Verify that an identical discovery payload does not trigger an entity update.

    Fires *data1* twice on the discovery topic and asserts that
    *discovery_update* is not called on the second fire.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        mqtt_mock_entry (MqttMockHAClientGenerator): Entry setup generator.
        domain (str): HA platform domain under test.
        data1 (str): JSON discovery payload string.
        discovery_update (MagicMock): Mock of the entity's discovery-update
            method whose ``called`` attribute is checked.
    """
    await mqtt_mock_entry()
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data1)
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.beer")
    assert state is not None
    assert state.name == "Beer"

    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data1)
    await hass.async_block_till_done()

    assert not discovery_update.called


async def help_test_discovery_broken(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    data1: str,
    data2: str,
) -> None:
    """Verify that a malformed discovery payload is rejected and a valid one still works.

    Fires *data1* (expected to fail validation) and asserts no ``beer`` entity
    is created, then fires *data2* (valid) and asserts the ``milk`` entity is
    created.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        mqtt_mock_entry (MqttMockHAClientGenerator): Entry setup generator.
        domain (str): HA platform domain under test.
        data1 (str): Invalid JSON discovery payload (entity named ``"Beer"``
            that should be rejected).
        data2 (str): Valid JSON discovery payload (entity named ``"Milk"``
            that should succeed).
    """
    await mqtt_mock_entry()
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data1)
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.beer")
    assert state is None

    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data2)
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.milk")
    assert state is not None
    assert state.name == "Milk"
    state = hass.states.get(f"{domain}.beer")
    assert state is None


async def help_test_encoding_subscribable_topics(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
    topic: str,
    value: Any,
    attribute: str | None = None,
    attribute_value: Any = None,
    init_payload: tuple[str, str] | None = None,
    skip_raw_test: bool = False,
) -> None:
    """Verify a subscribable topic correctly handles UTF-8, UTF-16, and raw-bytes encoding.

    Creates three discovery entities with different ``encoding`` settings
    (``"utf-8"``, ``"utf-16"``, ``""``) and fires the same logical value
    encoded appropriately for each, then asserts the resulting entity state
    or attribute value matches the expected output.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        mqtt_mock_entry (MqttMockHAClientGenerator): Entry setup generator.
        domain (str): HA platform domain under test.
        config (ConfigType): Base entity config dict.
        topic (str): Config key of the subscribable topic being tested
            (e.g. ``"state_topic"``).
        value (str): The string value to encode and publish.
        attribute (str | None): Entity attribute to read for the assertion,
            or ``None`` to read ``state.state``.
        attribute_value (Any): Expected attribute value, or ``None`` to use
            *value* directly.
        init_payload (tuple[str, str] | None): ``(topic_key, payload_string)``
            to fire before the test payload, e.g. to switch the device on.
        skip_raw_test (bool): When ``True``, skip the raw-bytes encoding test.
    """

    async def _test_encoding(
        hass: HomeAssistant,
        entity_id,
        topic,
        encoded_value,
        attribute,
        init_payload_topic,
        init_payload_value,
    ) -> Any:
        state = hass.states.get(entity_id)

        if init_payload_value:
            # Sometimes a device needs to have an initialization pay load, e.g. to switch the device on.
            async_fire_mqtt_message(hass, init_payload_topic, init_payload_value)
            await hass.async_block_till_done()

        state = hass.states.get(entity_id)

        async_fire_mqtt_message(hass, topic, encoded_value)
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state is not None

        if attribute:
            return state.attributes.get(attribute)

        return state.state if state else None

    init_payload_value_utf8 = None
    init_payload_value_utf16 = None
    # setup test1 default encoding
    config1 = copy.deepcopy(config)
    if domain == "device_tracker":
        config1["unique_id"] = "test1"
    else:
        config1["name"] = "test1"
    config1[topic] = "topic/test1"
    # setup test2 alternate encoding
    config2 = copy.deepcopy(config)
    if domain == "device_tracker":
        config2["unique_id"] = "test2"
    else:
        config2["name"] = "test2"
    config2["encoding"] = "utf-16"
    config2[topic] = "topic/test2"
    # setup test3 raw encoding
    config3 = copy.deepcopy(config)
    if domain == "device_tracker":
        config3["unique_id"] = "test3"
    else:
        config3["name"] = "test3"
    config3["encoding"] = ""
    config3[topic] = "topic/test3"

    if init_payload:
        config1[init_payload[0]] = "topic/init_payload1"
        config2[init_payload[0]] = "topic/init_payload2"
        config3[init_payload[0]] = "topic/init_payload3"
        init_payload_value_utf8 = init_payload[1].encode("utf-8")
        init_payload_value_utf16 = init_payload[1].encode("utf-16")

    await mqtt_mock_entry()
    async_fire_mqtt_message(
        hass, f"homeassistant/{domain}/item1/config", json.dumps(config1)
    )
    async_fire_mqtt_message(
        hass, f"homeassistant/{domain}/item2/config", json.dumps(config2)
    )
    async_fire_mqtt_message(
        hass, f"homeassistant/{domain}/item3/config", json.dumps(config3)
    )
    await hass.async_block_till_done()

    expected_result = attribute_value or value

    # test1 default encoding
    assert (
        await _test_encoding(
            hass,
            f"{domain}.test1",
            "topic/test1",
            value.encode("utf-8"),
            attribute,
            "topic/init_payload1",
            init_payload_value_utf8,
        )
        == expected_result
    )

    # test2 alternate encoding
    assert (
        await _test_encoding(
            hass,
            f"{domain}.test2",
            "topic/test2",
            value.encode("utf-16"),
            attribute,
            "topic/init_payload2",
            init_payload_value_utf16,
        )
        == expected_result
    )

    # test3 raw encoded input
    if skip_raw_test:
        return

    with suppress(AttributeError, TypeError, ValueError):
        result = await _test_encoding(
            hass,
            f"{domain}.test3",
            "topic/test3",
            value.encode("utf-16"),
            attribute,
            "topic/init_payload3",
            init_payload_value_utf16,
        )
        assert result != expected_result


async def help_test_entity_device_info_with_identifier(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
) -> None:
    """Verify device registry fields are populated from discovery config using identifiers.

    Discovers an entity with :data:`DEFAULT_CONFIG_DEVICE_INFO_ID` and asserts
    that name, manufacturer, model, hw_version, sw_version, area, and
    configuration_url are correctly written to the device registry.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        mqtt_mock_entry (MqttMockHAClientGenerator): Entry setup generator.
        domain (str): HA platform domain under test.
        config (ConfigType): Base entity config dict (device fields are injected).
    """
    await mqtt_mock_entry()
    # Add device settings to config
    config = copy.deepcopy(config[mqtt.DOMAIN][domain])
    config["device"] = copy.deepcopy(DEFAULT_CONFIG_DEVICE_INFO_ID)
    config["unique_id"] = "veryunique"

    area_registry = ar.async_get(hass)
    device_registry = dr.async_get(hass)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(mqtt.DOMAIN, "helloworld")})
    assert device is not None
    assert device.identifiers == {(mqtt.DOMAIN, "helloworld")}
    assert device.manufacturer == "Whatever"
    assert device.name == "Beer"
    assert device.model == "Glass"
    assert device.model_id == "XYZ001"
    assert device.hw_version == "rev1"
    assert device.sw_version == "0.1-beta"
    assert device.area_id == area_registry.async_get_area_by_name("default_area").id
    assert device.configuration_url == "http://example.com"


async def help_test_entity_device_info_with_connection(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
) -> None:
    """Verify device registry fields are populated from discovery config using MAC connection.

    Discovers an entity with :data:`DEFAULT_CONFIG_DEVICE_INFO_MAC` and asserts
    the connection tuple, name, manufacturer, model, and area are correctly
    written to the device registry.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        mqtt_mock_entry (MqttMockHAClientGenerator): Entry setup generator.
        domain (str): HA platform domain under test.
        config (ConfigType): Base entity config dict (device fields are injected).
    """
    await mqtt_mock_entry()
    # Add device settings to config
    config = copy.deepcopy(config[mqtt.DOMAIN][domain])
    config["device"] = copy.deepcopy(DEFAULT_CONFIG_DEVICE_INFO_MAC)
    config["unique_id"] = "veryunique"

    area_registry = ar.async_get(hass)
    device_registry = dr.async_get(hass)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, "02:5b:26:a8:dc:12")}
    )
    assert device is not None
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, "02:5b:26:a8:dc:12")}
    assert device.manufacturer == "Whatever"
    assert device.name == "Beer"
    assert device.model == "Glass"
    assert device.model_id == "XYZ001"
    assert device.hw_version == "rev1"
    assert device.sw_version == "0.1-beta"
    assert device.area_id == area_registry.async_get_area_by_name("default_area").id
    assert device.configuration_url == "http://example.com"


async def help_test_entity_device_info_remove(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
) -> None:
    """Verify that the device and entity registry entries are removed when an empty discovery payload is received.

    Discovers an entity and then fires an empty discovery payload; asserts
    both the entity and device registry entries are gone.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        mqtt_mock_entry (MqttMockHAClientGenerator): Entry setup generator.
        domain (str): HA platform domain under test.
        config (ConfigType): Base entity config dict (device fields are injected).
    """
    await mqtt_mock_entry()
    # Add device settings to config
    config = copy.deepcopy(config[mqtt.DOMAIN][domain])
    config["device"] = copy.deepcopy(DEFAULT_CONFIG_DEVICE_INFO_ID)
    config["unique_id"] = "veryunique"

    dev_registry = dr.async_get(hass)
    ent_registry = er.async_get(hass)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    device = dev_registry.async_get_device(identifiers={(mqtt.DOMAIN, "helloworld")})
    assert device is not None
    assert ent_registry.async_get_entity_id(domain, mqtt.DOMAIN, "veryunique")

    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", "")
    await hass.async_block_till_done()

    device = dev_registry.async_get_device(identifiers={(mqtt.DOMAIN, "helloworld")})
    assert device is None
    assert not ent_registry.async_get_entity_id(domain, mqtt.DOMAIN, "veryunique")


async def help_test_entity_device_info_update(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
) -> None:
    """Verify that device registry fields update when a discovery re-config changes them.

    Discovers an entity with name ``"Beer"``, then re-discovers with name
    ``"Milk"`` and asserts the device registry entry is updated.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        mqtt_mock_entry (MqttMockHAClientGenerator): Entry setup generator.
        domain (str): HA platform domain under test.
        config (ConfigType): Base entity config dict (device fields are injected).
    """
    await mqtt_mock_entry()
    # Add device settings to config
    config = copy.deepcopy(config[mqtt.DOMAIN][domain])
    config["device"] = copy.deepcopy(DEFAULT_CONFIG_DEVICE_INFO_ID)
    config["unique_id"] = "veryunique"

    registry = dr.async_get(hass)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device(identifiers={(mqtt.DOMAIN, "helloworld")})
    assert device is not None
    assert device.name == "Beer"

    config["device"]["name"] = "Milk"
    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device(identifiers={(mqtt.DOMAIN, "helloworld")})
    assert device is not None
    assert device.name == "Milk"


async def help_test_entity_name(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
    expected_friendly_name: str | None = None,
    device_class: str | None = None,
) -> None:
    """Verify entity naming with and without a device_class override.

    When *device_class* is supplied the entity ``name`` is removed from the
    config so HA derives the name from the device class.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        mqtt_mock_entry (MqttMockHAClientGenerator): Entry setup generator.
        domain (str): HA platform domain under test.
        config (ConfigType): Base entity config dict (device fields injected).
        expected_friendly_name (str | None): Expected ``state.name`` after
            ``"Beer "`` prefix is prepended, or ``None`` to skip assertion.
        device_class (str | None): Device class to set on the entity config,
            or ``None`` to use the configured name.
    """
    await mqtt_mock_entry()
    # Add device settings to config
    config = copy.deepcopy(config[mqtt.DOMAIN][domain])
    config["device"] = copy.deepcopy(DEFAULT_CONFIG_DEVICE_INFO_ID)
    config["unique_id"] = "veryunique"
    expected_entity_name = "test"
    if device_class is not None:
        config["device_class"] = device_class
        # Do not set a name
        config.pop("name")
        expected_entity_name = device_class

    registry = dr.async_get(hass)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({(mqtt.DOMAIN, "helloworld")})
    assert device is not None

    entity_id = f"{domain}.default_area_beer_{expected_entity_name}"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name == f"Beer {expected_friendly_name}"


async def help_test_entity_id_update_subscriptions(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
    topics: list[str] | None = None,
) -> None:
    """Verify MQTT subscriptions are re-registered when an entity_id is changed.

    Renames the entity from ``test`` to ``milk`` via the entity registry and
    asserts that all topic subscriptions are re-created for the new entity_id.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        mqtt_mock_entry (MqttMockHAClientGenerator): Entry setup generator.
        domain (str): HA platform domain under test.
        config (ConfigType): Base entity config dict (``unique_id`` injected).
        topics (list[str] | None): Expected subscription topics; defaults to
            ``["avty-topic", "test-topic"]`` if ``None``.
    """
    # Add unique_id to config
    config = copy.deepcopy(config)
    config[mqtt.DOMAIN][domain]["unique_id"] = "TOTALLY_UNIQUE"

    if topics is None:
        # Add default topics to config
        config[mqtt.DOMAIN][domain]["availability_topic"] = "avty-topic"
        config[mqtt.DOMAIN][domain]["state_topic"] = "test-topic"
        topics = ["avty-topic", "test-topic"]
    assert len(topics) > 0
    entity_registry = er.async_get(hass)

    with patch("homeassistant.config.load_yaml_config_file", return_value=config):
        mqtt_mock = await mqtt_mock_entry()
    assert mqtt_mock is not None

    state = hass.states.get(f"{domain}.test")
    assert state is not None
    assert (
        mqtt_mock.async_subscribe.call_count
        == len(topics)
        + 2 * len(SUPPORTED_COMPONENTS)
        + DISCOVERY_COUNT
        + DEVICE_DISCOVERY_COUNT
    )
    for topic in topics:
        mqtt_mock.async_subscribe.assert_any_call(
            topic, ANY, ANY, ANY, HassJobType.Callback
        )
    mqtt_mock.async_subscribe.reset_mock()

    entity_registry.async_update_entity(
        f"{domain}.test", new_entity_id=f"{domain}.milk"
    )
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.test")
    assert state is None

    state = hass.states.get(f"{domain}.milk")
    assert state is not None
    for topic in topics:
        mqtt_mock.async_subscribe.assert_any_call(
            topic, ANY, ANY, ANY, HassJobType.Callback
        )


async def help_test_entity_id_update_discovery_update(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
    topic: str | None = None,
) -> None:
    """Verify discovery re-config works correctly after an entity_id rename.

    Renames the entity then fires an updated discovery payload and verifies
    that the entity remains functional under its new id.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        mqtt_mock_entry (MqttMockHAClientGenerator): Entry setup generator.
        domain (str): HA platform domain under test.
        config (ConfigType): Base entity config dict (``unique_id`` injected).
        topic (str | None): Availability topic to subscribe to; defaults to
            ``"avty-topic"`` if ``None``.
    """
    # Add unique_id to config
    await mqtt_mock_entry()
    config = copy.deepcopy(config)
    config[mqtt.DOMAIN][domain]["unique_id"] = "TOTALLY_UNIQUE"

    if topic is None:
        # Add default topic to config
        config[mqtt.DOMAIN][domain]["availability_topic"] = "avty-topic"
        topic = "avty-topic"

    entity_registry = er.async_get(hass)
    data = json.dumps(config[mqtt.DOMAIN][domain])
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, topic, "online")
    state = hass.states.get(f"{domain}.test")
    assert state and state.state != STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, topic, "offline")
    state = hass.states.get(f"{domain}.test")
    assert state and state.state == STATE_UNAVAILABLE

    entity_registry.async_update_entity(
        f"{domain}.test", new_entity_id=f"{domain}.milk"
    )
    await hass.async_block_till_done()

    config[mqtt.DOMAIN][domain]["availability_topic"] = f"{topic}_2"
    data = json.dumps(config[mqtt.DOMAIN][domain])
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(domain)) == 1

    async_fire_mqtt_message(hass, f"{topic}_2", "online")
    state = hass.states.get(f"{domain}.milk")
    assert state and state.state != STATE_UNAVAILABLE


async def help_test_entity_icon_and_entity_picture(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
) -> None:
    """Verify entity icon and entity_picture are set from discovery config.

    Discovers three entity variants — no icon/picture, with entity_picture,
    and with icon — and asserts that each attribute is correctly set or absent.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        mqtt_mock_entry (MqttMockHAClientGenerator): Entry setup generator.
        domain (str): HA platform domain under test.
        config (ConfigType): Base entity config dict (device fields injected).
    """
    await mqtt_mock_entry()
    # Add device settings to config
    config = copy.deepcopy(config[mqtt.DOMAIN][domain])
    config["device"] = copy.deepcopy(DEFAULT_CONFIG_DEVICE_INFO_ID)

    ent_registry = er.async_get(hass)

    # Discover an entity without entity icon or picture
    unique_id = "veryunique1"
    config["unique_id"] = unique_id
    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/{unique_id}/config", data)
    await hass.async_block_till_done()
    entity_id = ent_registry.async_get_entity_id(domain, mqtt.DOMAIN, unique_id)
    state = hass.states.get(entity_id)
    assert entity_id is not None and state
    assert state.attributes.get("icon") is None
    assert state.attributes.get("entity_picture") is None

    # Discover an entity with an entity picture set
    unique_id = "veryunique2"
    config["entity_picture"] = "https://example.com/mypicture.png"
    config["unique_id"] = unique_id
    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/{unique_id}/config", data)
    await hass.async_block_till_done()
    entity_id = ent_registry.async_get_entity_id(domain, mqtt.DOMAIN, unique_id)
    state = hass.states.get(entity_id)
    assert entity_id is not None and state
    assert state.attributes.get("icon") is None
    assert state.attributes.get("entity_picture") == "https://example.com/mypicture.png"
    config.pop("entity_picture")

    # Discover an entity with an entity icon set
    unique_id = "veryunique3"
    config["icon"] = "mdi:emoji-happy-outline"
    config["unique_id"] = unique_id
    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/{unique_id}/config", data)
    await hass.async_block_till_done()
    entity_id = ent_registry.async_get_entity_id(domain, mqtt.DOMAIN, unique_id)
    state = hass.states.get(entity_id)
    assert entity_id is not None and state
    assert state.attributes.get("icon") == "mdi:emoji-happy-outline"
    assert state.attributes.get("entity_picture") is None


async def help_test_publishing_with_custom_encoding(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    domain: str,
    config: ConfigType,
    service: str,
    topic: str,
    parameters: dict[str, Any] | None,
    payload: str,
    template: str | None,
    tpl_par: str = "value",
    tpl_output: PublishPayloadType = None,
) -> None:
    """Verify payload encoding behaviour for a command-publishing service.

    Creates five discovery entities with different encoding configurations
    (UTF-8, UTF-16, raw/no encoding, invalid encoding, and template+raw),
    calls *service* on each, and asserts that the MQTT client receives the
    payload in the expected encoding or that the appropriate error is logged.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        mqtt_mock_entry (MqttMockHAClientGenerator): Entry setup generator.
        caplog (pytest.LogCaptureFixture): Log capture fixture for error
            assertion.
        domain (str): HA platform domain under test.
        config (ConfigType): Base entity config dict.
        service (str): The HA service name to call (e.g. ``"alarm_disarm"``).
        topic (str): Config key of the command topic (e.g.
            ``"command_topic"``).
        parameters (dict[str, Any] | None): Extra service call data beyond
            ``entity_id``, or ``None``.
        payload (str): The expected publish payload string.
        template (str | None): Config key of the command template to test with
            raw encoding, or ``None`` to skip that sub-test.
        tpl_par (str): Template variable name used in the template expression.
        tpl_output (PublishPayloadType): Expected output when the template
            renders with raw encoding, or ``None`` to use the default.
    """
    # prepare config for tests
    test_config: dict[str, dict[str, Any]] = {
        "test1": {"encoding": None, "cmd_tpl": False},
        "test2": {"encoding": "utf-16", "cmd_tpl": False},
        "test3": {"encoding": "", "cmd_tpl": False},
        "test4": {"encoding": "invalid", "cmd_tpl": False},
        "test5": {"encoding": "", "cmd_tpl": True},
    }
    setup_config = []
    service_data = {}
    for test_id, test_data in test_config.items():
        test_config_setup: dict[str, Any] = copy.copy(config[mqtt.DOMAIN][domain])
        test_config_setup.update(
            {
                topic: f"cmd/{test_id}",
                "name": f"{test_id}",
            }
        )
        if test_data["encoding"] is not None:
            test_config_setup["encoding"] = test_data["encoding"]
        if template and test_data["cmd_tpl"]:
            test_config_setup[template] = (
                f"{{{{ (('%.1f'|format({tpl_par}))[0] if is_number({tpl_par}) else {tpl_par}[0]) | ord | pack('b') }}}}"
            )
        setup_config.append(test_config_setup)

        # setup service data
        service_data[test_id] = {ATTR_ENTITY_ID: f"{domain}.{test_id}"}
        if parameters:
            service_data[test_id].update(parameters)

    # setup test entities using discovery
    mqtt_mock = await mqtt_mock_entry()
    for item, component_config in enumerate(setup_config):
        conf = json.dumps(component_config)
        async_fire_mqtt_message(
            hass, f"homeassistant/{domain}/component_{item}/config", conf
        )
    await hass.async_block_till_done()

    # 1) test with default encoding
    await hass.services.async_call(
        domain,
        service,
        service_data["test1"],
        blocking=True,
    )
    await hass.async_block_till_done()

    mqtt_mock.async_publish.assert_any_call("cmd/test1", str(payload), 0, False)
    mqtt_mock.async_publish.reset_mock()

    # 2) test with utf-16 encoding
    await hass.services.async_call(
        domain,
        service,
        service_data["test2"],
        blocking=True,
    )
    mqtt_mock.async_publish.assert_any_call(
        "cmd/test2", str(payload).encode("utf-16"), 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # 3) test with no encoding set should fail if payload is a string
    await hass.services.async_call(
        domain,
        service,
        service_data["test3"],
        blocking=True,
    )
    assert (
        f"Can't pass-through payload for publishing {payload} on cmd/test3 with no encoding set, need 'bytes'"
        in caplog.text
    )

    # 4) test with invalid encoding set should fail
    await hass.services.async_call(
        domain,
        service,
        service_data["test4"],
        blocking=True,
    )
    assert (
        f"Can't encode payload for publishing {payload} on cmd/test4 with encoding invalid"
        in caplog.text
    )

    # 5) test with command template and raw encoding if specified
    if not template:
        return

    await hass.services.async_call(
        domain,
        service,
        service_data["test5"],
        blocking=True,
    )
    mqtt_mock.async_publish.assert_any_call(
        "cmd/test5", tpl_output or str(payload)[0].encode("utf-8"), 0, False
    )
    mqtt_mock.async_publish.reset_mock()


async def help_test_reloadable(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    domain: str,
    config: ConfigType,
) -> None:
    """Verify that calling the reload service replaces YAML-configured entities.

    Starts the entry with two old entities, then triggers a reload with three
    new entities and asserts that only the new ones exist afterwards.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        mqtt_client_mock (MqttMockPahoClient): The mock paho client; its
            ``connect`` return value is set to ``0`` (success).
        domain (str): HA platform domain under test.
        config (ConfigType): Base entity config dict used to generate old and
            new entity configurations.
    """
    # Set up with empty config
    config = copy.deepcopy(config[mqtt.DOMAIN][domain])
    # Create and test an old config of 2 entities based on the config supplied
    old_config_1 = copy.deepcopy(config)
    old_config_1["name"] = "test_old_1"
    old_config_2 = copy.deepcopy(config)
    old_config_2["name"] = "test_old_2"

    old_config = {
        mqtt.DOMAIN: {domain: [old_config_1, old_config_2]},
    }
    # Start the MQTT entry with the old config
    entry = MockConfigEntry(
        domain=mqtt.DOMAIN,
        data={mqtt.CONF_BROKER: "test-broker"},
        version=mqtt.CONFIG_ENTRY_VERSION,
        minor_version=mqtt.CONFIG_ENTRY_MINOR_VERSION,
    )
    entry.add_to_hass(hass)
    mqtt_client_mock.connect.return_value = 0
    with patch("homeassistant.config.load_yaml_config_file", return_value=old_config):
        await hass.config_entries.async_setup(entry.entry_id)

    assert hass.states.get(f"{domain}.test_old_1")
    assert hass.states.get(f"{domain}.test_old_2")
    assert len(hass.states.async_all(domain)) == 2

    # Create temporary fixture for configuration.yaml based on the supplied config and
    # test a reload with this new config
    new_config_1 = copy.deepcopy(config)
    new_config_1["name"] = "test_new_1"
    new_config_2 = copy.deepcopy(config)
    new_config_2["name"] = "test_new_2"
    new_config_extra = copy.deepcopy(config)
    new_config_extra["name"] = "test_new_3"

    new_config = {
        mqtt.DOMAIN: {domain: [new_config_1, new_config_2, new_config_extra]},
    }
    with patch("homeassistant.config.load_yaml_config_file", return_value=new_config):
        # Reload the mqtt entry with the new config
        await hass.services.async_call(
            mqtt.DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all(domain)) == 3

    assert hass.states.get(f"{domain}.test_new_1")
    assert hass.states.get(f"{domain}.test_new_2")
    assert hass.states.get(f"{domain}.test_new_3")


async def help_test_unload_config_entry(hass: HomeAssistant) -> None:
    """Verify the locknalert_mqtt config entry unloads cleanly.

    Asserts the entry is currently ``LOADED``, calls ``async_unload``, and
    then asserts it transitions to ``NOT_LOADED``.

    Args:
        hass (HomeAssistant): The Home Assistant instance with a loaded
            locknalert_mqtt config entry.
    """
    mqtt_config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    assert mqtt_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mqtt_config_entry.entry_id)
    # work-a-round mypy bug https://github.com/python/mypy/issues/9005#issuecomment-1280985006
    updated_config_entry = mqtt_config_entry
    assert updated_config_entry.state is ConfigEntryState.NOT_LOADED
    await hass.async_block_till_done()


async def help_test_unload_config_entry_with_platform(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: dict[str, dict[str, Any]],
) -> None:
    """Verify that both YAML-configured and discovery-created entities are removed on unload.

    Sets up one entity via YAML and one via discovery, unloads the entry, and
    asserts both entities are gone.  Also verifies that a discovery message
    fired after unload does not recreate the entity.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        mqtt_mock_entry (MqttMockHAClientGenerator): Entry setup generator.
        domain (str): HA platform domain under test.
        config (dict[str, dict[str, Any]]): Base config used for both YAML and
            discovery setup.
    """
    # prepare setup through configuration.yaml
    config_setup: dict[str, dict[str, Any]] = copy.deepcopy(config)
    config_setup[mqtt.DOMAIN][domain]["name"] = "config_setup"
    config_name = config_setup

    with patch("homeassistant.config.load_yaml_config_file", return_value=config_name):
        await mqtt_mock_entry()

    # prepare setup through discovery
    discovery_setup = copy.deepcopy(config[mqtt.DOMAIN][domain])
    discovery_setup["name"] = "discovery_setup"
    async_fire_mqtt_message(
        hass, f"homeassistant/{domain}/bla/config", json.dumps(discovery_setup)
    )
    await hass.async_block_till_done()

    # check if both entities were setup correctly
    config_setup_entity = hass.states.get(f"{domain}.config_setup")
    assert config_setup_entity

    discovery_setup_entity = hass.states.get(f"{domain}.discovery_setup")
    assert discovery_setup_entity

    await help_test_unload_config_entry(hass)

    async_fire_mqtt_message(
        hass, f"homeassistant/{domain}/bla/config", json.dumps(discovery_setup)
    )
    await hass.async_block_till_done()

    # check if both entities were unloaded correctly
    config_setup_entity = hass.states.get(f"{domain}.{config_name}")
    assert config_setup_entity is None

    discovery_setup_entity = hass.states.get(f"{domain}.discovery_setup")
    assert discovery_setup_entity is None


async def help_test_skipped_async_ha_write_state(
    hass: HomeAssistant, topic: str, payload1: str, payload2: str
) -> None:
    """Verify ``async_write_ha_state`` is only called when the state actually changes.

    Fires *payload1* and asserts one write, then fires *payload2* (same value)
    and asserts no additional write, then fires *payload1* again and asserts
    another write.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        topic (str): MQTT topic to publish test payloads on.
        payload1 (str): First payload value.
        payload2 (str): Second payload value (expected to produce the same
            entity state as *payload1* so the write is skipped).
    """
    with patch(
        "homeassistant.components.locknalert_mqtt.entity.MqttEntity.async_write_ha_state"
    ) as mock_async_ha_write_state:
        assert len(mock_async_ha_write_state.mock_calls) == 0
        async_fire_mqtt_message(hass, topic, payload1)
        await hass.async_block_till_done()
        assert len(mock_async_ha_write_state.mock_calls) == 1

        async_fire_mqtt_message(hass, topic, payload1)
        await hass.async_block_till_done()
        assert len(mock_async_ha_write_state.mock_calls) == 1

        async_fire_mqtt_message(hass, topic, payload2)
        await hass.async_block_till_done()
        assert len(mock_async_ha_write_state.mock_calls) == 2

        async_fire_mqtt_message(hass, topic, payload2)
        await hass.async_block_till_done()
        assert len(mock_async_ha_write_state.mock_calls) == 2
