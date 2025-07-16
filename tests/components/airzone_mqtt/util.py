"""Tests for the Airzone integration."""

import json
from typing import Any
from unittest.mock import patch

from airzone_mqtt.const import AMT_ONLINE, AMT_RESPONSE, API_ONLINE

from homeassistant.components.airzone_mqtt.const import CONF_MQTT_TOPIC, DOMAIN
from homeassistant.components.mqtt.subscription import (  # pylint: disable=hass-component-root-import
    async_prepare_subscribe_topics,
    async_subscribe_topics,
    async_unsubscribe_topics,
)
from homeassistant.core import HomeAssistant, callback

from tests.common import MockConfigEntry, async_fire_mqtt_message
from tests.typing import MqttMockHAClient

CONFIG = {
    CONF_MQTT_TOPIC: "airzone-topic",
}


def airzone_topic(topic: str) -> str:
    """Generate Airzone MQTT topics."""
    return f"{CONFIG[CONF_MQTT_TOPIC]}/v1/{topic}"


def mock_az_get_status() -> str:
    """Mock MQTT az.get_status response."""
    data = {
        "headers": {
            "req_id": mock_cmd_req_id("az.get_status"),
            "origin": "airzone",
            "cmd": "az.get_status",
        },
        "body": {
            "devices": [
                {
                    "device_id": 0,
                    "device_type": "az_system",
                    "meta": {
                        "units": 0,
                    },
                    "parameters": {
                        "is_connected": True,
                    },
                    "system_id": 1,
                },
                {
                    "device_id": 1,
                    "device_type": "az_zone",
                    "meta": {
                        "units": 0,
                    },
                    "parameters": {
                        "air_active": False,
                        "humidity": 35,
                        "is_connected": True,
                        "mode": 3,
                        "mode_available": [0, 4, 3, 5, 2],
                        "name": "Room 1",
                        "power": False,
                        "rad_active": False,
                        "range_sp": {
                            "max": 30,
                            "min": 15,
                        },
                        "setpoint": 20.5,
                        "step": 0.5,
                        "zone_work_temp": 21.9,
                    },
                    "system_id": 1,
                },
                {
                    "device_id": 2,
                    "device_type": "az_zone",
                    "meta": {
                        "units": 0,
                    },
                    "parameters": {
                        "air_active": False,
                        "humidity": 44,
                        "is_connected": True,
                        "mode": 3,
                        "name": "Room 2",
                        "power": False,
                        "rad_active": False,
                        "range_sp": {
                            "max": 30,
                            "min": 15,
                        },
                        "setpoint": 21.5,
                        "step": 0.5,
                        "zone_work_temp": 22.6,
                    },
                    "system_id": 1,
                },
            ]
        },
    }

    return json.dumps(data)


def mock_cmd_req_id(topic: str) -> dict[str, Any]:
    """Mock MQTT cmd request id."""
    topic = topic.replace(".", "_")
    return f"test-req-id-{topic}"


def mock_online() -> str:
    """Mock MQTT online response."""
    data = {
        API_ONLINE: True,
    }

    return json.dumps(data)


async def async_init_integration(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Set up the Airzone MQTT integration in Home Assistant."""

    config_entry = MockConfigEntry(
        data=CONFIG,
        entry_id="401fc1ef025f9514a8e2533be7fabbbb",
        domain=DOMAIN,
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.airzone_mqtt.AirzoneMqttApi.cmd_req_id",
            side_effect=mock_cmd_req_id,
        ),
    ):

        @callback
        def mqtt_invoke(*args):
            """Record calls."""
            async_fire_mqtt_message(
                hass=hass,
                topic=airzone_topic(AMT_ONLINE),
                payload=mock_online(),
            )
            async_fire_mqtt_message(
                hass=hass,
                topic=airzone_topic(f"{AMT_RESPONSE}/az_get_status"),
                payload=mock_az_get_status(),
            )

        sub_state = None
        sub_state = async_prepare_subscribe_topics(
            hass,
            sub_state,
            {
                "az_get_status": {
                    "topic": f"{CONFIG[CONF_MQTT_TOPIC]}/v1/invoke",
                    "msg_callback": mqtt_invoke,
                },
            },
        )
        await async_subscribe_topics(hass, sub_state)

        await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

        async_unsubscribe_topics(hass, sub_state)
