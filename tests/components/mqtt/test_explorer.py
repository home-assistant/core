"""Test the MQTT explorer websocket API."""

import json
from typing import Any
from unittest.mock import ANY

import pytest
from pytest_homeassistant.common import MockUser, async_fire_mqtt_message
from pytest_homeassistant.components.mqtt.common import MOCK_SENSOR_SUBENTRY_DATA
from pytest_homeassistant.typing import MqttMockHAClientGenerator, WebSocketGenerator

from homeassistant.components import button, light, mqtt, sensor
from homeassistant.components.mqtt.const import DOMAIN
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
    EntityStateAttribute,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

YAML_LIGHT_CONFIG = {
    "name": "Kitchen",
    "unique_id": "kitchen_light",
    "command_topic": "kitchen/light/set",
    "state_topic": "kitchen/light/state",
    "qos": 1,
    "device": {
        "identifiers": ["yaml_device"],
        "name": "YAML device",
        "via_device": "yaml_parent",
    },
}
YAML_SENSOR_CONFIG = {"name": "Outside", "state_topic": "outside/temperature"}
# A unique ID in YAML can be a number, the entity registry has it as a string
YAML_BUTTON_CONFIG = {"name": "Bell", "unique_id": 1234, "command_topic": "bell/set"}

ORIGIN = {
    "name": "Zigbee2MQTT",
    "sw_version": "2.0",
    "support_url": "https://www.zigbee2mqtt.io",
}
DISCOVERY_SENSOR_TOPIC = "homeassistant/sensor/z2m_temperature/config"
DISCOVERY_SENSOR_CONFIG = {
    "name": "Temperature",
    "unique_id": "z2m_temperature",
    "state_topic": "z2m/temperature",
    "device": {"identifiers": ["z2m_device"], "name": "Z2M device"},
    "origin": ORIGIN,
}
DISCOVERY_CHILD_SENSOR_TOPIC = "homeassistant/sensor/z2m_node/z2m_child/config"
DISCOVERY_CHILD_SENSOR_CONFIG = {
    "name": "Humidity",
    "unique_id": "z2m_child_humidity",
    "state_topic": "z2m/child/humidity",
    "device": {
        "identifiers": ["z2m_device"],
        "child_device": {"identifiers": ["z2m_child"], "name": "Child"},
    },
    "origin": ORIGIN,
}
DISCOVERY_TRIGGER_TOPIC = "homeassistant/device_automation/z2m_button/config"
DISCOVERY_TRIGGER_CONFIG = {
    "automation_type": "trigger",
    "device": {"identifiers": ["z2m_device"]},
    "topic": "z2m/action",
    "type": "button_short_press",
    "subtype": "button_1",
    "origin": ORIGIN,
}
DISCOVERY_TAG_TOPIC = "homeassistant/tag/z2m_tag/config"
DISCOVERY_TAG_CONFIG = {"topic": "z2m/tag", "device": {"identifiers": ["z2m_device"]}}
DEVICE_DISCOVERY_TOPIC = "homeassistant/device/z2m_plug/config"
DEVICE_DISCOVERY_CONFIG = {
    "device": {"identifiers": ["z2m_plug"], "name": "Plug"},
    "origin": ORIGIN,
    "components": {
        "power": {
            "platform": "sensor",
            "unique_id": "z2m_plug_power",
            "state_topic": "z2m/plug/power",
        },
        "action": {
            "platform": "device_automation",
            "automation_type": "trigger",
            "topic": "z2m/plug/action",
            "type": "button_short_press",
            "subtype": "button_1",
        },
    },
}
DISCOVERY_BINARY_SENSOR_TOPIC = "homeassistant/binary_sensor/door/config"
DISCOVERY_BINARY_SENSOR_CONFIG = {
    "name": "Door",
    "unique_id": "door",
    "state_topic": "door/state",
}

SETUP_PARAMETERS = (
    "hass_config",
    "mqtt_config_subentries_data",
)
SETUP_VALUES = [
    (
        {
            mqtt.DOMAIN: {
                button.DOMAIN: YAML_BUTTON_CONFIG,
                light.DOMAIN: YAML_LIGHT_CONFIG,
                sensor.DOMAIN: YAML_SENSOR_CONFIG,
            }
        },
        (
            ConfigSubentryData(
                data=MOCK_SENSOR_SUBENTRY_DATA,
                subentry_type="device",
                title="Mock subentry",
            ),
        ),
    )
]


async def _async_setup(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Set up MQTT items from YAML, a subentry and discovery, and send messages."""
    await mqtt_mock_entry()
    for topic, config in (
        (DISCOVERY_SENSOR_TOPIC, DISCOVERY_SENSOR_CONFIG),
        (DISCOVERY_CHILD_SENSOR_TOPIC, DISCOVERY_CHILD_SENSOR_CONFIG),
        (DISCOVERY_TRIGGER_TOPIC, DISCOVERY_TRIGGER_CONFIG),
        (DISCOVERY_TAG_TOPIC, DISCOVERY_TAG_CONFIG),
        (DISCOVERY_BINARY_SENSOR_TOPIC, DISCOVERY_BINARY_SENSOR_CONFIG),
    ):
        async_fire_mqtt_message(hass, topic, json.dumps(config))
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "kitchen/light/state", "ON")
    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.yaml_device_kitchen"},
        blocking=True,
    )
    await hass.async_block_till_done()


def _device_id(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, identifier: str
) -> str:
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, identifier), hass.config_entries.async_entries(DOMAIN)[0].entry_id
    )
    assert device is not None
    return device.id


def _subentry_id(hass: HomeAssistant) -> str:
    return next(iter(hass.config_entries.async_entries(DOMAIN)[0].subentries))


@pytest.mark.parametrize(SETUP_PARAMETERS, SETUP_VALUES)
async def test_structure(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the structure has every source, device, entity, topic and artifact."""
    await _async_setup(hass, mqtt_mock_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    subentry_id = _subentry_id(hass)
    yaml_device_id = _device_id(hass, device_registry, "yaml_device")
    yaml_parent_device_id = _device_id(hass, device_registry, "yaml_parent")
    z2m_device_id = _device_id(hass, device_registry, "z2m_device")
    subentry_device_id = _device_id(hass, device_registry, subentry_id)
    z2m_child_device = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, "z2m_child"), entry.entry_id
    )
    assert z2m_child_device is not None
    # Earlier discovered items stay in the registry when their discovery is gone
    stale_device_id = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "stale")}, name="Stale"
    ).id
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "empty")}, name="Empty"
    )
    for unique_id, device_id, original_name in (
        ("orphan", None, "Orphan"),
        ("stale_entity", stale_device_id, "Stale entity"),
        ("z2m_restored", z2m_device_id, None),
    ):
        entity_registry.async_get_or_create(
            sensor.DOMAIN,
            DOMAIN,
            unique_id,
            config_entry=entry,
            device_id=device_id,
            original_name=original_name,
            suggested_object_id=unique_id,
        )
    hass.states.async_set(
        "sensor.z2m_restored",
        STATE_UNAVAILABLE,
        {
            EntityStateAttribute.FRIENDLY_NAME: "Restored",
            EntityStateAttribute.RESTORED: True,
        },
    )

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "mqtt/explorer/structure"})
    response = await client.receive_json()

    assert response["success"]
    result = response["result"]
    assert result["broker"] == {
        "connected": True,
        "host": "mock-broker",
        "port": 1883,
    }
    assert result["sources"] == [
        {"id": "discovery", "type": "discovery", "title": None, "sw_version": None},
        {
            "id": "origin:Zigbee2MQTT",
            "type": "discovery",
            "title": "Zigbee2MQTT",
            "sw_version": "2.0",
        },
        {
            "id": f"subentry:{subentry_id}",
            "type": "subentry",
            "title": "Mock subentry",
            "sw_version": None,
        },
        {"id": "yaml", "type": "yaml", "title": None, "sw_version": None},
    ]
    assert sorted(result["devices"], key=lambda item: item["name"]) == [
        {
            "device_id": z2m_child_device.id,
            "name": "Child",
            "sources": ["origin:Zigbee2MQTT"],
            "via_device_id": z2m_device_id,
            "child_device": True,
        },
        # The stub via device gets the sources of the devices linked to it
        {
            "device_id": yaml_parent_device_id,
            "name": "MQTT",
            "sources": ["yaml"],
            "via_device_id": None,
            "child_device": False,
        },
        {
            "device_id": subentry_device_id,
            "name": "Milk notifier",
            "sources": [f"subentry:{subentry_id}"],
            "via_device_id": None,
            "child_device": False,
        },
        # A device with only entities that were not set up goes under discovery,
        # a device without any entities is left out
        {
            "device_id": stale_device_id,
            "name": "Stale",
            "sources": ["discovery"],
            "via_device_id": None,
            "child_device": False,
        },
        {
            "device_id": yaml_device_id,
            "name": "YAML device",
            "sources": ["yaml"],
            "via_device_id": yaml_parent_device_id,
            "child_device": False,
        },
        {
            "device_id": z2m_device_id,
            "name": "Z2M device",
            "sources": ["discovery", "origin:Zigbee2MQTT"],
            "via_device_id": None,
            "child_device": False,
        },
    ]
    assert result["entities"] == [
        {
            "entity_id": "binary_sensor.door",
            "name": "Door",
            "available": True,
            "source": "discovery",
            "device_id": None,
            "node_id": None,
            "topics": [{"topic": "door/state", "direction": "subscribe", "qos": 0}],
        },
        # Publish topics only show up after the first publish
        {
            "entity_id": "button.bell",
            "name": "Bell",
            "available": True,
            "source": "yaml",
            "device_id": None,
            "node_id": None,
            "topics": [],
        },
        {
            "entity_id": "light.yaml_device_kitchen",
            "name": "YAML device Kitchen",
            "available": True,
            "source": "yaml",
            "device_id": yaml_device_id,
            "node_id": None,
            "topics": [
                {"topic": "kitchen/light/state", "direction": "subscribe", "qos": 1},
                {"topic": "kitchen/light/set", "direction": "publish", "qos": 1},
            ],
        },
        # Set up, but unavailable until it receives a state
        {
            "entity_id": "sensor.milk_notifier_energy",
            "name": "Milk notifier Energy",
            "available": False,
            "source": f"subentry:{subentry_id}",
            "device_id": subentry_device_id,
            "node_id": None,
            "topics": [{"topic": "test-topic", "direction": "subscribe", "qos": 0}],
        },
        # Not set up and without a device: under "No linked device" of discovery
        {
            "entity_id": "sensor.orphan",
            "name": "Orphan",
            "available": False,
            "source": "discovery",
            "device_id": None,
            "node_id": None,
            "topics": [],
        },
        {
            "entity_id": "sensor.outside",
            "name": "Outside",
            "available": True,
            "source": "yaml",
            "device_id": None,
            "node_id": None,
            "topics": [
                {"topic": "outside/temperature", "direction": "subscribe", "qos": 0}
            ],
        },
        # Not set up, with a device: the origin is unknown, it goes under its device
        {
            "entity_id": "sensor.stale_entity",
            "name": "Stale entity",
            "available": False,
            "source": None,
            "device_id": stale_device_id,
            "node_id": None,
            "topics": [],
        },
        {
            "entity_id": "sensor.z2m_device_child_humidity",
            "name": "Child Humidity",
            "available": True,
            "source": "origin:Zigbee2MQTT",
            "device_id": z2m_child_device.id,
            "node_id": "z2m_node",
            "topics": [
                {"topic": "z2m/child/humidity", "direction": "subscribe", "qos": 0}
            ],
        },
        {
            "entity_id": "sensor.z2m_device_temperature",
            "name": "Z2M device Temperature",
            "available": True,
            "source": "origin:Zigbee2MQTT",
            "device_id": z2m_device_id,
            "node_id": None,
            "topics": [
                {"topic": "z2m/temperature", "direction": "subscribe", "qos": 0}
            ],
        },
        {
            "entity_id": "sensor.z2m_restored",
            "name": "Restored",
            "available": False,
            "source": None,
            "device_id": z2m_device_id,
            "node_id": None,
            "topics": [],
        },
    ]
    assert result["artifacts"] == [
        {
            "artifact_id": "device_trigger:z2m_button",
            "type": "device_trigger",
            "source": "origin:Zigbee2MQTT",
            "device_id": z2m_device_id,
            "node_id": None,
            "topics": [{"topic": "z2m/action", "direction": "subscribe", "qos": 0}],
        },
        {
            "artifact_id": "tag:z2m_tag",
            "type": "tag",
            "source": "discovery",
            "device_id": z2m_device_id,
            "node_id": None,
            "topics": [{"topic": "z2m/tag", "direction": "subscribe", "qos": 0}],
        },
    ]


@pytest.mark.parametrize(SETUP_PARAMETERS, SETUP_VALUES)
async def test_entity_details(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the details of entities from every source."""
    await _async_setup(hass, mqtt_mock_entry)
    subentry_id = _subentry_id(hass)
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {"type": "mqtt/explorer/details", "entity_id": "light.yaml_device_kitchen"}
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "configs": [
            {
                "source": "yaml",
                "type": "yaml",
                "discovery_topic": None,
                "origin": None,
                "payload": YAML_LIGHT_CONFIG,
                "device_discovery": False,
            }
        ],
        "topics": [
            {
                "topic": "kitchen/light/state",
                "direction": "subscribe",
                "qos": 1,
                "messages": [
                    {
                        "payload": "ON",
                        "qos": 0,
                        "retain": False,
                        "time": ANY,
                        "topic": "kitchen/light/state",
                    }
                ],
            },
            {
                "topic": "kitchen/light/set",
                "direction": "publish",
                "qos": 1,
                "messages": [
                    {
                        "payload": "ON",
                        "qos": 1,
                        "retain": False,
                        "time": ANY,
                        "topic": "kitchen/light/set",
                    }
                ],
            },
        ],
    }

    await client.send_json_auto_id(
        {"type": "mqtt/explorer/details", "entity_id": "sensor.z2m_device_temperature"}
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["configs"] == [
        {
            "source": "origin:Zigbee2MQTT",
            "type": "discovery",
            "discovery_topic": DISCOVERY_SENSOR_TOPIC,
            "origin": ORIGIN,
            "payload": DISCOVERY_SENSOR_CONFIG,
            "device_discovery": False,
        }
    ]

    await client.send_json_auto_id(
        {"type": "mqtt/explorer/details", "entity_id": "sensor.milk_notifier_energy"}
    )
    response = await client.receive_json()
    assert response["success"]
    component = next(iter(MOCK_SENSOR_SUBENTRY_DATA["components"].values()))
    assert response["result"]["configs"] == [
        {
            "source": f"subentry:{subentry_id}",
            "type": "subentry",
            "discovery_topic": None,
            "origin": None,
            "payload": component,
            "device_discovery": False,
        }
    ]

    await client.send_json_auto_id(
        {"type": "mqtt/explorer/details", "entity_id": "button.bell"}
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["configs"] == [
        {
            "source": "yaml",
            "type": "yaml",
            "discovery_topic": None,
            "origin": None,
            "payload": YAML_BUTTON_CONFIG,
            "device_discovery": False,
        }
    ]

    # A YAML entity without a unique ID cannot be matched to its config
    await client.send_json_auto_id(
        {"type": "mqtt/explorer/details", "entity_id": "sensor.outside"}
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["configs"] == []
    assert response["result"]["topics"] == [
        {
            "topic": "outside/temperature",
            "direction": "subscribe",
            "qos": 0,
            "messages": [],
        }
    ]

    # An earlier discovered entity that was not set up has no config or topics
    entity_registry.async_get_or_create(
        sensor.DOMAIN,
        DOMAIN,
        "orphan",
        config_entry=hass.config_entries.async_entries(DOMAIN)[0],
        suggested_object_id="orphan",
    )
    await client.send_json_auto_id(
        {"type": "mqtt/explorer/details", "entity_id": "sensor.orphan"}
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "configs": [],
        "topics": [],
    }


@pytest.mark.parametrize(SETUP_PARAMETERS, SETUP_VALUES)
async def test_device_details(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the details of a device with items from more than one source."""
    await _async_setup(hass, mqtt_mock_entry)
    z2m_device_id = _device_id(hass, device_registry, "z2m_device")
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {"type": "mqtt/explorer/details", "device_id": z2m_device_id}
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "configs": [
            {
                "source": "discovery",
                "type": "discovery",
                "discovery_topic": DISCOVERY_TAG_TOPIC,
                "origin": None,
                "payload": DISCOVERY_TAG_CONFIG["device"],
                "device_discovery": False,
            },
            {
                "source": "origin:Zigbee2MQTT",
                "type": "discovery",
                "discovery_topic": DISCOVERY_SENSOR_TOPIC,
                "origin": ORIGIN,
                "payload": DISCOVERY_SENSOR_CONFIG["device"],
                "device_discovery": False,
            },
        ],
        "topics": [],
    }

    subentry_id = _subentry_id(hass)
    await client.send_json_auto_id(
        {
            "type": "mqtt/explorer/details",
            "device_id": _device_id(hass, device_registry, subentry_id),
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["configs"] == [
        {
            "source": f"subentry:{subentry_id}",
            "type": "subentry",
            "discovery_topic": None,
            "origin": None,
            "payload": MOCK_SENSOR_SUBENTRY_DATA["device"],
            "device_discovery": False,
        }
    ]


@pytest.mark.parametrize(SETUP_PARAMETERS, SETUP_VALUES)
async def test_artifact_details(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test the details of a device trigger."""
    await _async_setup(hass, mqtt_mock_entry)
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {"type": "mqtt/explorer/details", "artifact_id": "device_trigger:z2m_button"}
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "configs": [
            {
                "source": "origin:Zigbee2MQTT",
                "type": "discovery",
                "discovery_topic": DISCOVERY_TRIGGER_TOPIC,
                "origin": ORIGIN,
                "payload": DISCOVERY_TRIGGER_CONFIG,
                "device_discovery": False,
            }
        ],
        # The debug info keeps no messages for device triggers
        "topics": [
            {
                "topic": "z2m/action",
                "direction": "subscribe",
                "qos": 0,
                "messages": [],
            }
        ],
    }


async def test_device_discovery_details(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the details of a device from a device based discovery payload."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(
        hass, DEVICE_DISCOVERY_TOPIC, json.dumps(DEVICE_DISCOVERY_CONFIG)
    )
    await hass.async_block_till_done()
    client = await hass_ws_client(hass)

    # The device discovery payload is built again from its components
    await client.send_json_auto_id(
        {
            "type": "mqtt/explorer/details",
            "device_id": _device_id(hass, device_registry, "z2m_plug"),
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["configs"] == [
        {
            "source": "origin:Zigbee2MQTT",
            "type": "discovery",
            "discovery_topic": DEVICE_DISCOVERY_TOPIC,
            "origin": ORIGIN,
            "payload": DEVICE_DISCOVERY_CONFIG,
            "device_discovery": True,
        }
    ]

    # An entity has its own component config, with the device and origin
    entity_id = entity_registry.async_get_entity_id(
        sensor.DOMAIN, DOMAIN, "z2m_plug_power"
    )
    await client.send_json_auto_id(
        {"type": "mqtt/explorer/details", "entity_id": entity_id}
    )
    response = await client.receive_json()
    assert response["success"]
    component = dict(DEVICE_DISCOVERY_CONFIG["components"]["power"])
    component.pop("platform")
    assert response["result"]["configs"] == [
        {
            "source": "origin:Zigbee2MQTT",
            "type": "discovery",
            "discovery_topic": DEVICE_DISCOVERY_TOPIC,
            "origin": ORIGIN,
            "payload": component
            | {"device": DEVICE_DISCOVERY_CONFIG["device"], "origin": ORIGIN},
            "device_discovery": True,
        }
    ]


async def test_topic_qos_update(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test the QoS of a topic the entity subscribes to twice follows an update."""
    await mqtt_mock_entry()
    config = {
        "name": "Shared",
        "unique_id": "shared",
        "state_topic": "shared/topic",
        "json_attributes_topic": "shared/topic",
    }
    topic = "homeassistant/sensor/shared/config"
    async_fire_mqtt_message(hass, topic, json.dumps(config))
    await hass.async_block_till_done()
    # The old subscription is still counted when the new one is added
    async_fire_mqtt_message(hass, topic, json.dumps(config | {"qos": 1}))
    await hass.async_block_till_done()
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "mqtt/explorer/structure"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["entities"][0]["topics"] == [
        {"topic": "shared/topic", "direction": "subscribe", "qos": 1}
    ]


@pytest.mark.parametrize(
    "item",
    [
        pytest.param({"entity_id": "sensor.unknown"}, id="entity"),
        pytest.param({"device_id": "unknown"}, id="device"),
        pytest.param({"artifact_id": "tag:unknown"}, id="artifact"),
    ],
)
async def test_details_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    item: dict[str, str],
) -> None:
    """Test details of an unknown item."""
    await mqtt_mock_entry()
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "mqtt/explorer/details"} | item)
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "not_found"


@pytest.mark.parametrize(
    "message",
    [
        pytest.param({}, id="no_item"),
        pytest.param(
            {"entity_id": "sensor.test", "device_id": "abc"}, id="more_than_one_item"
        ),
    ],
)
async def test_details_invalid(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    message: dict[str, str],
) -> None:
    """Test details need exactly one item."""
    await mqtt_mock_entry()
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "mqtt/explorer/details"} | message)
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_format"


@pytest.mark.parametrize(
    "message",
    [
        pytest.param({"type": "mqtt/explorer/structure"}, id="structure"),
        pytest.param(
            {"type": "mqtt/explorer/details", "entity_id": "sensor.test"},
            id="details",
        ),
    ],
)
async def test_not_loaded(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    message: dict[str, Any],
) -> None:
    """Test the commands when MQTT is not loaded."""
    await mqtt_mock_entry()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await hass.config_entries.async_unload(entry.entry_id)
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(message)
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "not_loaded"


@pytest.mark.parametrize(
    "message",
    [
        pytest.param({"type": "mqtt/explorer/structure"}, id="structure"),
        pytest.param(
            {"type": "mqtt/explorer/details", "entity_id": "sensor.test"},
            id="details",
        ),
    ],
)
async def test_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    hass_admin_user: MockUser,
    message: dict[str, Any],
) -> None:
    """Test the commands need an admin user."""
    await mqtt_mock_entry()
    hass_admin_user.groups = []
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(message)
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "unauthorized"
