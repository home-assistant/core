"""The tests for MQTT child devices."""

import json
from typing import Any
from unittest.mock import DEFAULT, AsyncMock, call

import probatio
import pytest
from pytest_homeassistant.common import async_fire_mqtt_message
from pytest_homeassistant.typing import MqttMockHAClientGenerator, WebSocketGenerator

from homeassistant.components.mqtt.const import DOMAIN
from homeassistant.components.mqtt.models import DATA_MQTT
from homeassistant.components.mqtt.schemas import (
    MQTT_DEVICE_INFO_SCHEMA,
    MQTT_ENTITY_DEVICE_INFO_SCHEMA,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

PARENT_DEVICE = {"identifiers": ["parent"], "name": "Parent", "manufacturer": "Acme"}
CHILD_DEVICE = {"identifiers": ["sub"], "name": "Sub"}
SWITCH_ENTITY_ID = "switch.parent_sub_switch"
SWITCH_TOPIC = "homeassistant/switch/sw1/config"
DEVICE_TOPIC = "homeassistant/device/parent/config"
REGISTRATION_WARNING = "Unable to register MQTT device"
UNIQUE_ID_REQUIRED = "'unique_id' is required when a 'child_device' is configured"
TRIGGER_TOPIC = "homeassistant/device_automation/trigger1/config"
TRIGGER_CONFIG = {
    "automation_type": "trigger",
    "topic": "button1",
    "type": "button_short_press",
    "subtype": "button_1",
}
TAG_TOPIC = "homeassistant/tag/tag1/config"
DISCOVERY_SWITCH = {
    "p": "switch",
    "name": "Switch",
    "cmd_t": "sw/set",
    "uniq_id": "sw1",
}


def _entry_id(hass: HomeAssistant) -> str:
    """Return the MQTT config entry id."""
    return hass.config_entries.async_entries(DOMAIN)[0].entry_id


def _get_device(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, identifier: str
) -> dr.DeviceEntry | None:
    """Return the main device with the identifier."""
    return device_registry.async_get_device_by_identifier(
        (DOMAIN, identifier), _entry_id(hass)
    )


def _get_child_device(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, identifier: str
) -> dr.ChildDeviceEntry | None:
    """Return the child device with the identifier."""
    return device_registry.async_get_child_device_by_identifier(
        (DOMAIN, identifier), _entry_id(hass)
    )


def _switch_config(unique_id: str, device: dict[str, Any], name: str = "Switch") -> str:
    """Return a single component switch discovery payload."""
    return json.dumps(
        {
            "name": name,
            "command_topic": f"{unique_id}/set",
            "unique_id": unique_id,
            "device": device,
        }
    )


async def _discover_switch(
    hass: HomeAssistant, unique_id: str, device: dict[str, Any], name: str = "Switch"
) -> None:
    """Send a single component switch discovery message."""
    async_fire_mqtt_message(
        hass,
        f"homeassistant/switch/{unique_id}/config",
        _switch_config(unique_id, device, name),
    )
    await hass.async_block_till_done()


def test_child_device_schema() -> None:
    """Test a valid child device config."""
    assert MQTT_ENTITY_DEVICE_INFO_SCHEMA(
        {"identifiers": ["parent"], "child_device": {"identifiers": "sub"}}
    )["child_device"] == {"identifiers": ["sub"]}


@pytest.mark.parametrize(
    ("schema", "child_device"),
    [
        pytest.param(MQTT_ENTITY_DEVICE_INFO_SCHEMA, {}, id="no_identifiers"),
        pytest.param(
            MQTT_ENTITY_DEVICE_INFO_SCHEMA, {"identifiers": []}, id="empty_identifiers"
        ),
        pytest.param(
            MQTT_ENTITY_DEVICE_INFO_SCHEMA,
            {"identifiers": ["sub"], "via_device": "hub"},
            id="device_option",
        ),
        pytest.param(
            MQTT_DEVICE_INFO_SCHEMA, {"identifiers": ["sub"]}, id="not_supported"
        ),
    ],
)
def test_invalid_child_device_schema(
    schema: probatio.All, child_device: dict[str, Any]
) -> None:
    """Test an invalid child device config."""
    with pytest.raises(probatio.Invalid):
        schema({"identifiers": ["parent"], "child_device": child_device})


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(
            _switch_config("sw1", {**PARENT_DEVICE, "child_device": CHILD_DEVICE}),
            id="full",
        ),
        pytest.param(
            json.dumps(
                {
                    "name": "Switch",
                    "cmd_t": "sw1/set",
                    "uniq_id": "sw1",
                    "dev": {
                        "ids": ["parent"],
                        "name": "Parent",
                        "mf": "Acme",
                        "cdev": {"ids": ["sub"], "name": "Sub"},
                    },
                }
            ),
            id="abbreviated",
        ),
    ],
)
async def test_single_component_discovery_with_child_device(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    payload: str,
) -> None:
    """Test the entity is linked to the child device of the parent device."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(hass, SWITCH_TOPIC, payload)
    await hass.async_block_till_done()

    parent = _get_device(hass, device_registry, "parent")
    assert parent is not None
    assert parent.name == "Parent"
    assert parent.manufacturer == "Acme"
    child_device = _get_child_device(hass, device_registry, "sub")
    assert child_device is not None
    assert child_device.name == "Sub"
    assert child_device.parent_device_id == parent.id

    entity_entry = entity_registry.async_get(SWITCH_ENTITY_ID)
    assert entity_entry is not None
    assert entity_entry.device_id == child_device.id


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(
            {
                "device": {"identifiers": ["parent"], "name": "Parent"},
                "origin": {"name": "Foo2Mqtt"},
                "child_devices": [
                    {
                        "identifiers": ["sub1"],
                        "name": "Sub 1",
                        "components": {
                            "switch1": {
                                "platform": "switch",
                                "name": "Switch",
                                "command_topic": "switch1/set",
                                "unique_id": "switch1",
                            }
                        },
                    },
                    {
                        "identifiers": ["sub2"],
                        "name": "Sub 2",
                        "components": {
                            "switch2": {
                                "platform": "switch",
                                "name": "Switch",
                                "command_topic": "switch2/set",
                                "unique_id": "switch2",
                            }
                        },
                    },
                ],
                "components": {
                    "rssi": {
                        "platform": "sensor",
                        "name": "RSSI",
                        "state_topic": "rssi",
                        "unique_id": "rssi",
                    },
                },
            },
            id="full",
        ),
        pytest.param(
            {
                "dev": {"ids": ["parent"], "name": "Parent"},
                "o": {"name": "Foo2Mqtt"},
                "cdevs": [
                    {
                        "ids": ["sub1"],
                        "name": "Sub 1",
                        "cmps": {
                            "switch1": {
                                "p": "switch",
                                "name": "Switch",
                                "cmd_t": "switch1/set",
                                "uniq_id": "switch1",
                            }
                        },
                    },
                    {
                        "ids": ["sub2"],
                        "name": "Sub 2",
                        "cmps": {
                            "switch2": {
                                "p": "switch",
                                "name": "Switch",
                                "cmd_t": "switch2/set",
                                "uniq_id": "switch2",
                            }
                        },
                    },
                ],
                "cmps": {
                    "rssi": {
                        "p": "sensor",
                        "name": "RSSI",
                        "stat_t": "rssi",
                        "uniq_id": "rssi",
                    },
                },
            },
            id="abbreviated",
        ),
    ],
)
async def test_device_discovery_with_child_device(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    payload: dict[str, Any],
) -> None:
    """Test the child devices and their components in device based discovery."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(hass, DEVICE_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()

    parent = _get_device(hass, device_registry, "parent")
    child_device_1 = _get_child_device(hass, device_registry, "sub1")
    child_device_2 = _get_child_device(hass, device_registry, "sub2")
    assert parent is not None
    assert child_device_1 is not None
    assert child_device_2 is not None
    assert child_device_1.parent_device_id == parent.id
    assert child_device_2.parent_device_id == parent.id

    switch_1 = entity_registry.async_get("switch.parent_sub_1_switch")
    switch_2 = entity_registry.async_get("switch.parent_sub_2_switch")
    rssi = entity_registry.async_get("sensor.parent_rssi")
    assert switch_1 is not None
    assert switch_2 is not None
    assert rssi is not None
    assert switch_1.device_id == child_device_1.id
    assert switch_2.device_id == child_device_2.id
    # The shared device config is not altered by the child devices
    assert rssi.device_id == parent.id


async def test_device_discovery_with_child_devices_only(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test device based discovery without components of the device itself."""
    await mqtt_mock_entry()
    payload = {
        "dev": {"ids": ["parent"], "name": "Parent"},
        "o": {"name": "Foo2Mqtt"},
        "cdevs": [{"ids": ["sub"], "name": "Sub", "cmps": {"sw": DISCOVERY_SWITCH}}],
    }
    async_fire_mqtt_message(hass, DEVICE_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()

    child_device = _get_child_device(hass, device_registry, "sub")
    assert child_device is not None
    assert _get_device(hass, device_registry, "parent") is not None
    entity_entry = entity_registry.async_get(SWITCH_ENTITY_ID)
    assert entity_entry is not None
    assert entity_entry.device_id == child_device.id


@pytest.mark.parametrize(
    ("payload", "error"),
    [
        pytest.param(
            {"dev": {"ids": ["parent"]}, "o": {"name": "Foo2Mqtt"}},
            "At least one of 'components' or 'child_devices' is required",
            id="no_components",
        ),
        pytest.param(
            {
                "dev": {"ids": ["parent"]},
                "o": {"name": "Foo2Mqtt"},
                "cdevs": [{"ids": ["sub"], "cmps": {"sw": DISCOVERY_SWITCH}}],
                "cmps": {"sw": DISCOVERY_SWITCH},
            },
            "Duplicate component IDs: sw",
            id="duplicate_component_id_device_and_child",
        ),
        pytest.param(
            {
                "dev": {"ids": ["parent"]},
                "o": {"name": "Foo2Mqtt"},
                "cdevs": [
                    {"ids": ["sub1"], "cmps": {"sw": DISCOVERY_SWITCH}},
                    {"ids": ["sub2"], "cmps": {"sw": DISCOVERY_SWITCH}},
                ],
            },
            "Duplicate component IDs: sw",
            id="duplicate_component_id_children",
        ),
        pytest.param(
            {
                "dev": {"ids": ["parent"]},
                "o": {"name": "Foo2Mqtt"},
                "cdevs": [
                    {"ids": ["sub"], "cmps": {"sw1": DISCOVERY_SWITCH}},
                    {"ids": ["sub"], "cmps": {"sw2": DISCOVERY_SWITCH}},
                ],
            },
            "Duplicate child device identifiers: sub",
            id="duplicate_child_identifiers",
        ),
        pytest.param(
            {
                "dev": {"ids": ["parent"]},
                "o": {"name": "Foo2Mqtt"},
                "cdevs": [{"ids": ["parent"], "cmps": {"sw": DISCOVERY_SWITCH}}],
            },
            "Child device identifiers must differ from the device identifiers: parent",
            id="child_identifiers_of_device",
        ),
        pytest.param(
            {"dev": {"ids": ["parent"]}, "o": {"name": "Foo2Mqtt"}, "cdevs": ["sub"]},
            "at 'child_devices[0]'",
            id="child_not_a_mapping",
        ),
        pytest.param(
            {"dev": {"ids": ["parent"]}, "o": {"name": "Foo2Mqtt"}, "cdevs": 1},
            "at 'child_devices'",
            id="child_devices_not_a_list",
        ),
        pytest.param(
            {
                "dev": {"ids": ["parent"]},
                "o": {"name": "Foo2Mqtt"},
                "cdevs": [{"cmps": {"sw": DISCOVERY_SWITCH}}],
            },
            "required key not provided",
            id="child_without_identifiers",
        ),
        pytest.param(
            {
                "dev": {"ids": ["parent"]},
                "o": {"name": "Foo2Mqtt"},
                "cdevs": [{"ids": ["sub"]}],
            },
            "required key not provided",
            id="child_without_components",
        ),
        pytest.param(
            {
                "dev": {"ids": ["parent"]},
                "o": {"name": "Foo2Mqtt"},
                "cdevs": [
                    {
                        "ids": ["sub"],
                        "mf": "Acme",
                        "cmps": {"sw": DISCOVERY_SWITCH},
                    }
                ],
            },
            "not a valid option",
            id="child_with_device_option",
        ),
        pytest.param(
            {
                "dev": {"ids": ["parent"]},
                "o": {"name": "Foo2Mqtt"},
                "cdevs": [
                    {
                        "ids": ["sub"],
                        "cmps": {
                            "trigger1": {"p": "device_automation", **TRIGGER_CONFIG}
                        },
                    }
                ],
            },
            "value must be one of",
            id="child_device_trigger",
        ),
        pytest.param(
            {
                "dev": {"ids": ["parent"]},
                "o": {"name": "Foo2Mqtt"},
                "cdevs": [
                    {"ids": ["sub"], "cmps": {"tag1": {"p": "tag", "topic": "tag1"}}}
                ],
            },
            "value must be one of",
            id="child_tag",
        ),
    ],
)
async def test_invalid_device_discovery_child_devices(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
    payload: dict[str, Any],
    error: str,
) -> None:
    """Test invalid child devices in device based discovery are rejected."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(hass, DEVICE_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()

    assert "Invalid MQTT device discovery payload for parent" in caplog.text
    assert error in caplog.text
    assert not device_registry.devices


async def test_device_discovery_update_child_devices(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test moving and removing components of child devices with device discovery."""
    await mqtt_mock_entry()
    device = {"ids": ["parent"], "name": "Parent"}
    origin = {"name": "Foo2Mqtt"}
    payload: dict[str, Any] = {
        "dev": device,
        "o": origin,
        "cmps": {"sw": DISCOVERY_SWITCH},
    }
    async_fire_mqtt_message(hass, DEVICE_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()
    parent = _get_device(hass, device_registry, "parent")
    assert parent is not None
    entity_id = "switch.parent_switch"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.device_id == parent.id

    # Move the component from the device to a child device
    payload = {
        "dev": device,
        "o": origin,
        "cdevs": [{"ids": ["sub"], "name": "Sub", "cmps": {"sw": DISCOVERY_SWITCH}}],
    }
    async_fire_mqtt_message(hass, DEVICE_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()
    child_device = _get_child_device(hass, device_registry, "sub")
    assert child_device is not None
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.device_id == child_device.id

    # Remove the component, the child device and its parent are cleaned up
    payload = {
        "dev": device,
        "o": origin,
        "cdevs": [{"ids": ["sub"], "cmps": {"sw": {"p": "switch"}}}],
    }
    async_fire_mqtt_message(hass, DEVICE_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()
    assert entity_registry.async_get(entity_id) is None
    assert _get_child_device(hass, device_registry, "sub") is None
    assert _get_device(hass, device_registry, "parent") is None


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            DOMAIN: {
                "switch": [
                    {
                        "name": "Switch",
                        "command_topic": "sw1/set",
                        "unique_id": "sw1",
                        "device": {**PARENT_DEVICE, "child_device": CHILD_DEVICE},
                    }
                ]
            }
        }
    ],
)
async def test_yaml_with_child_device(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a manually configured entity on a child device."""
    await mqtt_mock_entry()

    parent = _get_device(hass, device_registry, "parent")
    child_device = _get_child_device(hass, device_registry, "sub")
    assert parent is not None
    assert child_device is not None
    assert child_device.parent_device_id == parent.id
    entity_entry = entity_registry.async_get(SWITCH_ENTITY_ID)
    assert entity_entry is not None
    assert entity_entry.device_id == child_device.id


async def test_discovery_without_unique_id_ignores_device(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the device config is ignored for an entity without unique ID."""
    await mqtt_mock_entry()
    payload = {
        "name": "Switch",
        "command_topic": "sw1/set",
        "device": {**PARENT_DEVICE, "via_device": "hub"},
    }
    async_fire_mqtt_message(hass, SWITCH_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()
    # Discovery update
    payload["name"] = "Updated"
    async_fire_mqtt_message(hass, SWITCH_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()

    state = hass.states.get("switch.switch")
    assert state is not None
    assert state.name == "Updated"
    assert not device_registry.devices


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            DOMAIN: {
                "switch": [
                    {
                        "name": "Switch",
                        "command_topic": "sw1/set",
                        "device": {**PARENT_DEVICE, "via_device": "hub"},
                    }
                ]
            }
        }
    ],
)
async def test_yaml_without_unique_id_ignores_device(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the device config is ignored for a YAML entity without unique ID."""
    await mqtt_mock_entry()

    assert hass.states.get("switch.switch") is not None
    assert not device_registry.devices


async def test_discovery_child_device_requires_unique_id(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a discovered child device requires a unique ID."""
    await mqtt_mock_entry()
    payload = {
        "name": "Switch",
        "command_topic": "sw1/set",
        "device": {**PARENT_DEVICE, "child_device": CHILD_DEVICE},
    }
    async_fire_mqtt_message(hass, SWITCH_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()

    assert UNIQUE_ID_REQUIRED in caplog.text
    assert hass.states.get("switch.switch") is None
    assert not device_registry.devices


async def test_discovery_update_child_device_requires_unique_id(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a discovery update adding a child device requires a unique ID."""
    await mqtt_mock_entry()
    payload: dict[str, Any] = {"name": "Switch", "command_topic": "sw1/set"}
    async_fire_mqtt_message(hass, SWITCH_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()
    assert hass.states.get("switch.switch") is not None

    payload["name"] = "Updated"
    payload["device"] = {**PARENT_DEVICE, "child_device": CHILD_DEVICE}
    async_fire_mqtt_message(hass, SWITCH_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()

    assert UNIQUE_ID_REQUIRED in caplog.text
    state = hass.states.get("switch.switch")
    assert state is not None
    assert state.name == "Switch"
    assert not device_registry.devices


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            DOMAIN: {
                "switch": [
                    {
                        "name": "Switch",
                        "command_topic": "sw1/set",
                        "device": {**PARENT_DEVICE, "child_device": CHILD_DEVICE},
                    },
                    {
                        "name": "Other",
                        "command_topic": "other/set",
                        "unique_id": "other",
                    },
                ]
            }
        }
    ],
)
async def test_yaml_child_device_requires_unique_id(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a manually configured child device requires a unique ID."""
    await mqtt_mock_entry()

    assert UNIQUE_ID_REQUIRED in caplog.text
    assert hass.states.get("switch.switch") is None
    assert hass.states.get("switch.other") is not None
    assert not device_registry.devices


async def test_child_device_not_allowed_in_device_discovery_device(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a child device is rejected in the shared device of device discovery."""
    await mqtt_mock_entry()
    payload = {
        "dev": {"ids": ["parent"], "name": "Parent", "cdev": {"ids": ["sub"]}},
        "o": {"name": "Foo2Mqtt"},
        "cmps": {
            "switch1": {
                "p": "switch",
                "cmd_t": "switch1/set",
                "uniq_id": "switch1",
            },
        },
    }
    async_fire_mqtt_message(hass, DEVICE_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()

    assert "Invalid MQTT device discovery payload for parent" in caplog.text
    assert _get_device(hass, device_registry, "parent") is None
    assert _get_child_device(hass, device_registry, "sub") is None


@pytest.mark.parametrize(
    ("topic", "payload"),
    [
        pytest.param(
            "homeassistant/device_automation/trigger1/config",
            {
                "automation_type": "trigger",
                "topic": "button1",
                "type": "button_short_press",
                "subtype": "button_1",
                "dev": {"ids": ["parent"], "cdev": {"ids": ["sub"]}},
            },
            id="device_trigger",
        ),
        pytest.param(
            "homeassistant/tag/tag1/config",
            {
                "topic": "tag1",
                "dev": {"ids": ["parent"], "cdev": {"ids": ["sub"]}},
            },
            id="tag",
        ),
    ],
)
@pytest.mark.usefixtures("tag_mock")
async def test_child_device_not_supported_for_device_triggers_and_tags(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
    topic: str,
    payload: dict[str, Any],
) -> None:
    """Test device triggers and tags reject a child device."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(hass, topic, json.dumps(payload))
    await hass.async_block_till_done()

    assert "not a valid option" in caplog.text
    assert "at 'device.child_device'" in caplog.text
    assert _get_device(hass, device_registry, "parent") is None
    assert _get_child_device(hass, device_registry, "sub") is None


async def test_discovery_update_child_device(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a discovery update adds, changes and removes the child device."""
    await mqtt_mock_entry()
    await _discover_switch(hass, "sw1", PARENT_DEVICE)
    parent = _get_device(hass, device_registry, "parent")
    assert parent is not None
    entity_id = "switch.parent_switch"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.device_id == parent.id

    # Add a child device
    await _discover_switch(
        hass, "sw1", {**PARENT_DEVICE, "child_device": {"identifiers": ["sub1"]}}
    )
    child_device_1 = _get_child_device(hass, device_registry, "sub1")
    assert child_device_1 is not None
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.device_id == child_device_1.id

    # Change the child device, the old child device is cleaned up
    await _discover_switch(
        hass, "sw1", {**PARENT_DEVICE, "child_device": {"identifiers": ["sub2"]}}
    )
    child_device_2 = _get_child_device(hass, device_registry, "sub2")
    assert child_device_2 is not None
    assert _get_child_device(hass, device_registry, "sub1") is None
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.device_id == child_device_2.id

    # Remove the child device, the entity moves back to the parent device
    await _discover_switch(hass, "sw1", PARENT_DEVICE)
    assert _get_child_device(hass, device_registry, "sub2") is None
    assert _get_device(hass, device_registry, "parent") == parent
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.device_id == parent.id


async def test_cleanup_parent_device_with_child_device(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a parent device is kept while it has child devices."""
    await mqtt_mock_entry()
    await _discover_switch(hass, "on_parent", PARENT_DEVICE)
    await _discover_switch(
        hass, "on_sub", {**PARENT_DEVICE, "child_device": CHILD_DEVICE}
    )
    assert _get_device(hass, device_registry, "parent") is not None
    assert _get_child_device(hass, device_registry, "sub") is not None

    # Removing the last entity of the parent device keeps the parent device,
    # as removing it would also remove its child device
    async_fire_mqtt_message(hass, "homeassistant/switch/on_parent/config", "")
    await hass.async_block_till_done()
    assert _get_device(hass, device_registry, "parent") is not None
    assert _get_child_device(hass, device_registry, "sub") is not None

    # Removing the last entity of the child device also cleans up the parent device
    async_fire_mqtt_message(hass, "homeassistant/switch/on_sub/config", "")
    await hass.async_block_till_done()
    assert _get_child_device(hass, device_registry, "sub") is None
    assert _get_device(hass, device_registry, "parent") is None


async def test_remove_child_device_keeps_device_discovery_topic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test removing a child device keeps the components of the other devices."""
    mqtt_mock = await mqtt_mock_entry()
    payload = {
        "dev": {"ids": ["parent"], "name": "Parent"},
        "o": {"name": "Foo2Mqtt"},
        "cdevs": [
            {
                "ids": ["sub1"],
                "name": "Sub 1",
                "cmps": {"sw1": {**DISCOVERY_SWITCH, "uniq_id": "sw1"}},
            },
            {
                "ids": ["sub2"],
                "name": "Sub 2",
                "cmps": {"sw2": {**DISCOVERY_SWITCH, "uniq_id": "sw2"}},
            },
        ],
        "cmps": {"sw": {**DISCOVERY_SWITCH, "uniq_id": "sw"}},
    }
    async_fire_mqtt_message(hass, DEVICE_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()
    child_device_1 = _get_child_device(hass, device_registry, "sub1")
    assert child_device_1 is not None
    mqtt_mock.async_publish.reset_mock()

    device_registry.async_remove_device(child_device_1.id)
    await hass.async_block_till_done()
    assert not entity_registry.async_is_registered("switch.parent_sub_1_switch")
    assert entity_registry.async_is_registered("switch.parent_sub_2_switch")
    assert entity_registry.async_is_registered("switch.parent_switch")
    assert _get_device(hass, device_registry, "parent") is not None
    assert (
        "Although entity switch.parent_sub_1_switch was removed from Home Assistant"
        in caplog.text
    )
    # Clearing the device discovery topic would remove all device components
    mqtt_mock.async_publish.assert_not_called()

    # The child device is discovered again with the next device discovery payload
    async_fire_mqtt_message(hass, DEVICE_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()
    assert _get_child_device(hass, device_registry, "sub1") is not None
    assert entity_registry.async_is_registered("switch.parent_sub_1_switch")

    # Removing the parent device also removes its child devices and clears the topic
    parent = _get_device(hass, device_registry, "parent")
    assert parent is not None
    device_registry.async_remove_device(parent.id)
    await hass.async_block_till_done()
    assert _get_child_device(hass, device_registry, "sub1") is None
    assert _get_child_device(hass, device_registry, "sub2") is None
    assert not entity_registry.async_is_registered("switch.parent_sub_2_switch")
    mqtt_mock.async_publish.assert_any_call(
        DEVICE_TOPIC, None, 0, True, message_expiry_interval=None
    )


async def test_remove_last_child_device_keeps_parent_device(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test removing the last child device keeps a parent without components.

    Removing the parent device afterwards clears the topic.
    """
    mqtt_mock = await mqtt_mock_entry()
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)
    payload = {
        "dev": {"ids": ["parent"], "name": "Parent"},
        "o": {"name": "Foo2Mqtt"},
        "cdevs": [
            {
                "ids": ["sub"],
                "name": "Sub",
                "cmps": {
                    "sw1": {**DISCOVERY_SWITCH, "name": "Switch 1", "uniq_id": "sw1"},
                    "sw2": {**DISCOVERY_SWITCH, "name": "Switch 2", "uniq_id": "sw2"},
                },
            }
        ],
    }
    async_fire_mqtt_message(hass, DEVICE_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()
    child_device = _get_child_device(hass, device_registry, "sub")
    assert child_device is not None
    assert len(er.async_entries_for_device(entity_registry, child_device.id)) == 2
    mqtt_mock.async_publish.reset_mock()

    # The entities of the child device are removed together, cleaning up the parent
    # after the first entity would clear the topic when the next one is removed
    device_registry.async_remove_device(child_device.id)
    await hass.async_block_till_done()
    parent = _get_device(hass, device_registry, "parent")
    assert parent is not None
    mqtt_mock.async_publish.assert_not_called()

    # The parent device has no entities left that clear the topic when removed
    response = await ws_client.remove_device(parent.id)
    assert response["success"]
    await hass.async_block_till_done()
    assert _get_device(hass, device_registry, "parent") is None
    mqtt_mock.async_publish.assert_any_call(
        DEVICE_TOPIC, None, 0, True, message_expiry_interval=None
    )


@pytest.mark.parametrize(
    "enabled_by_default",
    [pytest.param(True, id="enabled"), pytest.param(False, id="disabled")],
)
async def test_remove_old_parent_device_keeps_moved_device_discovery_topic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
    enabled_by_default: bool,
) -> None:
    """Test removing the old device of a kept topic after it moved to another device.

    The old device is kept by an entity of another discovery topic. A disabled
    entity is not added, but is linked to its new device as well.
    """
    mqtt_mock = await mqtt_mock_entry()
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)
    await _discover_switch(hass, "keeper", {"identifiers": ["parent"]}, name="Keeper")
    component = {**DISCOVERY_SWITCH, "en": enabled_by_default}
    payload: dict[str, Any] = {
        "dev": {"ids": ["parent"], "name": "Parent"},
        "o": {"name": "Foo2Mqtt"},
        "cdevs": [{"ids": ["sub"], "name": "Sub", "cmps": {"sw": component}}],
    }
    async_fire_mqtt_message(hass, DEVICE_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()
    child_device = _get_child_device(hass, device_registry, "sub")
    assert child_device is not None
    device_registry.async_remove_device(child_device.id)
    await hass.async_block_till_done()

    # The components of the kept topic are discovered again with another device
    payload["dev"] = {"ids": ["new_parent"], "name": "New parent"}
    async_fire_mqtt_message(hass, DEVICE_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()
    child_device = _get_child_device(hass, device_registry, "sub")
    assert child_device is not None
    new_parent = _get_device(hass, device_registry, "new_parent")
    assert new_parent is not None
    assert child_device.parent_device_id == new_parent.id
    parent = _get_device(hass, device_registry, "parent")
    assert parent is not None
    mqtt_mock.async_publish.reset_mock()

    response = await ws_client.remove_device(parent.id)
    assert response["success"]
    await hass.async_block_till_done()
    assert entity_registry.async_get_entity_id("switch", DOMAIN, "sw1") is not None
    assert (
        call(DEVICE_TOPIC, None, 0, True, message_expiry_interval=None)
        not in mqtt_mock.async_publish.call_args_list
    )


async def test_remove_parent_device_skips_forgotten_device_discovery_topic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a kept topic forgotten while clearing another topic is not cleared."""
    mqtt_mock = await mqtt_mock_entry()
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)
    other_topic = "homeassistant/device/parent_other/config"
    for topic, child_id, component_id in (
        (DEVICE_TOPIC, "sub1", "sw1"),
        (other_topic, "sub2", "sw2"),
    ):
        payload = {
            "dev": {"ids": ["parent"], "name": "Parent"},
            "o": {"name": "Foo2Mqtt"},
            "cdevs": [
                {
                    "ids": [child_id],
                    "cmps": {
                        component_id: {**DISCOVERY_SWITCH, "uniq_id": component_id}
                    },
                }
            ],
        }
        async_fire_mqtt_message(hass, topic, json.dumps(payload))
        await hass.async_block_till_done()
        child_device = _get_child_device(hass, device_registry, child_id)
        assert child_device is not None
        device_registry.async_remove_device(child_device.id)
        await hass.async_block_till_done()
    parent = _get_device(hass, device_registry, "parent")
    assert parent is not None
    mqtt_mock.async_publish.reset_mock()

    def forget_other_topic(*args: Any, **kwargs: Any) -> Any:
        """Simulate a rediscovery of the other topic while publishing."""
        hass.data[DATA_MQTT].retained_device_discovery_topics.pop(other_topic, None)
        return DEFAULT

    mqtt_mock.async_publish.side_effect = forget_other_topic
    response = await ws_client.remove_device(parent.id)
    assert response["success"]
    await hass.async_block_till_done()
    mqtt_mock.async_publish.assert_called_once_with(
        DEVICE_TOPIC, None, 0, True, message_expiry_interval=None
    )


async def test_remove_parent_device_with_child_device_components_clears_topic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test removing a parent device without components of its own clears the topic.

    The child devices and their entities are removed before the parent device.
    """
    mqtt_mock = await mqtt_mock_entry()
    payload = {
        "dev": {"ids": ["parent"], "name": "Parent"},
        "o": {"name": "Foo2Mqtt"},
        "cdevs": [{"ids": ["sub"], "name": "Sub", "cmps": {"sw": DISCOVERY_SWITCH}}],
    }
    async_fire_mqtt_message(hass, DEVICE_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()
    parent = _get_device(hass, device_registry, "parent")
    assert parent is not None
    mqtt_mock.async_publish.reset_mock()

    device_registry.async_remove_device(parent.id)
    await hass.async_block_till_done()
    assert not entity_registry.async_is_registered(SWITCH_ENTITY_ID)
    mqtt_mock.async_publish.assert_any_call(
        DEVICE_TOPIC, None, 0, True, message_expiry_interval=None
    )


async def test_remove_entity_without_child_device_keeps_device_discovery_topic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test removing an entity of a child device that could not be registered."""
    mqtt_mock = await mqtt_mock_entry()
    # A device registered in this session can not be used as a child device
    await _discover_switch(hass, "old", {"identifiers": ["sub"], "name": "Old"})
    payload = {
        "dev": {"ids": ["parent"], "name": "Parent"},
        "o": {"name": "Foo2Mqtt"},
        "cdevs": [{"ids": ["sub"], "name": "Sub", "cmps": {"sw1": DISCOVERY_SWITCH}}],
        "cmps": {"sw2": {**DISCOVERY_SWITCH, "uniq_id": "sw2"}},
    }
    async_fire_mqtt_message(hass, DEVICE_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()
    assert REGISTRATION_WARNING in caplog.text
    entity_id = entity_registry.async_get_entity_id("switch", DOMAIN, "sw1")
    assert entity_id is not None
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.device_id is None
    mqtt_mock.async_publish.reset_mock()

    entity_registry.async_remove(entity_id)
    await hass.async_block_till_done()
    assert entity_registry.async_is_registered("switch.parent_switch")
    # Clearing the device discovery topic would remove all device components
    mqtt_mock.async_publish.assert_not_called()


async def test_remove_child_device_after_failed_parent_update(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test removing a child device after its parent device could not be changed."""
    mqtt_mock = await mqtt_mock_entry()
    payload: dict[str, Any] = {
        "dev": {"ids": ["parent"], "name": "Parent"},
        "o": {"name": "Foo2Mqtt"},
        "cdevs": [
            {
                "ids": ["sub1"],
                "name": "Sub 1",
                "cmps": {"sw1": {**DISCOVERY_SWITCH, "uniq_id": "sw1"}},
            },
            {
                "ids": ["sub2"],
                "name": "Sub 2",
                "cmps": {"sw2": {**DISCOVERY_SWITCH, "uniq_id": "sw2"}},
            },
        ],
    }
    async_fire_mqtt_message(hass, DEVICE_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()
    child_device_1 = _get_child_device(hass, device_registry, "sub1")
    assert child_device_1 is not None

    # The child devices can not be moved to another parent device
    payload["dev"] = {"ids": ["new_parent"], "name": "New parent"}
    async_fire_mqtt_message(hass, DEVICE_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()
    assert REGISTRATION_WARNING in caplog.text
    assert _get_device(hass, device_registry, "new_parent") is None
    switch_1 = entity_registry.async_get("switch.parent_sub_1_switch")
    assert switch_1 is not None
    assert switch_1.device_id == child_device_1.id
    mqtt_mock.async_publish.reset_mock()

    device_registry.async_remove_device(child_device_1.id)
    await hass.async_block_till_done()
    assert entity_registry.async_is_registered("switch.parent_sub_2_switch")
    # Clearing the device discovery topic would remove all device components
    mqtt_mock.async_publish.assert_not_called()


async def test_remove_parent_device_after_failed_move_to_existing_parent(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test removing the parent device after its child devices could not be moved.

    The device the child devices were moved to exists, but is not their parent.
    """
    mqtt_mock = await mqtt_mock_entry()
    await _discover_switch(hass, "other", {"identifiers": ["other"], "name": "Other"})
    payload: dict[str, Any] = {
        "dev": {"ids": ["parent"], "name": "Parent"},
        "o": {"name": "Foo2Mqtt"},
        "cdevs": [{"ids": ["sub"], "name": "Sub", "cmps": {"sw": DISCOVERY_SWITCH}}],
    }
    async_fire_mqtt_message(hass, DEVICE_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()

    payload["dev"] = {"ids": ["other"], "name": "Other"}
    async_fire_mqtt_message(hass, DEVICE_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()
    assert REGISTRATION_WARNING in caplog.text
    assert _get_device(hass, device_registry, "other") is not None
    parent = _get_device(hass, device_registry, "parent")
    assert parent is not None
    mqtt_mock.async_publish.reset_mock()

    device_registry.async_remove_device(parent.id)
    await hass.async_block_till_done()
    assert not entity_registry.async_is_registered(SWITCH_ENTITY_ID)
    mqtt_mock.async_publish.assert_any_call(
        DEVICE_TOPIC, None, 0, True, message_expiry_interval=None
    )


async def test_rejected_entity_cleans_up_devices(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the devices of a rejected entity with a duplicate unique ID are removed."""
    await mqtt_mock_entry()
    await _discover_switch(
        hass, "first", {**PARENT_DEVICE, "child_device": CHILD_DEVICE}
    )
    payload = _switch_config(
        "first",
        {
            "identifiers": ["other_parent"],
            "child_device": {"identifiers": ["other_child"]},
        },
    )
    async_fire_mqtt_message(hass, "homeassistant/switch/second/config", payload)
    await hass.async_block_till_done()

    assert "ID first already exists" in caplog.text
    assert _get_device(hass, device_registry, "other_parent") is None
    assert _get_child_device(hass, device_registry, "other_child") is None
    # The devices of the entity that was added first are kept
    assert _get_device(hass, device_registry, "parent") is not None
    assert _get_child_device(hass, device_registry, "sub") is not None


async def test_disabled_entity_keeps_device(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the device of an entity that is disabled by default is kept."""
    await mqtt_mock_entry()
    payload = json.loads(
        _switch_config("sw1", {**PARENT_DEVICE, "child_device": CHILD_DEVICE})
    )
    payload["enabled_by_default"] = False
    async_fire_mqtt_message(hass, SWITCH_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()

    child_device = _get_child_device(hass, device_registry, "sub")
    assert child_device is not None
    assert _get_device(hass, device_registry, "parent") is not None
    entity_entry = entity_registry.async_get(SWITCH_ENTITY_ID)
    assert entity_entry is not None
    assert entity_entry.disabled
    assert entity_entry.device_id == child_device.id


async def test_disabled_entity_rediscovery_cleans_up_old_child_device(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the old child device of a rediscovered disabled entity is cleaned up."""
    await mqtt_mock_entry()
    payload = json.loads(
        _switch_config("sw1", {**PARENT_DEVICE, "child_device": CHILD_DEVICE})
    )
    payload["enabled_by_default"] = False
    async_fire_mqtt_message(hass, SWITCH_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()
    assert _get_child_device(hass, device_registry, "sub") is not None

    payload["device"]["child_device"] = {"identifiers": ["sub2"], "name": "Sub 2"}
    async_fire_mqtt_message(hass, SWITCH_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()
    new_child_device = _get_child_device(hass, device_registry, "sub2")
    assert new_child_device is not None
    entity_entry = entity_registry.async_get(SWITCH_ENTITY_ID)
    assert entity_entry is not None
    assert entity_entry.device_id == new_child_device.id
    assert _get_child_device(hass, device_registry, "sub") is None


async def test_discovery_update_child_device_keeps_disabled_entity(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test moving an entity to another child device keeps a disabled entity."""
    await mqtt_mock_entry()
    await _discover_switch(hass, "sw1", {**PARENT_DEVICE, "child_device": CHILD_DEVICE})
    await _discover_switch(
        hass, "sw2", {**PARENT_DEVICE, "child_device": CHILD_DEVICE}, name="Other"
    )
    child_device = _get_child_device(hass, device_registry, "sub")
    assert child_device is not None
    disabled_entity_id = "switch.parent_sub_other"
    entity_registry.async_update_entity(
        disabled_entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()

    await _discover_switch(
        hass,
        "sw1",
        {**PARENT_DEVICE, "child_device": {"identifiers": ["sub2"], "name": "Sub 2"}},
    )
    assert _get_child_device(hass, device_registry, "sub2") is not None
    # The old child device is kept, as removing it would remove the disabled entity
    assert _get_child_device(hass, device_registry, "sub") is not None
    entity_entry = entity_registry.async_get(disabled_entity_id)
    assert entity_entry is not None
    assert entity_entry.device_id == child_device.id


async def test_child_device_registration_error(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a child device that can not be registered.

    The identifiers of a device registered in this session can not be
    used for a child device.
    """
    await mqtt_mock_entry()
    await _discover_switch(hass, "old", {"identifiers": ["sub"], "name": "Old"})
    old_device = _get_device(hass, device_registry, "sub")
    assert old_device is not None

    await _discover_switch(
        hass, "new", {**PARENT_DEVICE, "child_device": CHILD_DEVICE}, name="New"
    )
    assert REGISTRATION_WARNING in caplog.text
    assert not [record for record in caplog.records if record.exc_info]
    # The entity is added without a device and the parent device is cleaned up
    new_entry = entity_registry.async_get("switch.new")
    assert new_entry is not None
    assert new_entry.device_id is None
    assert _get_device(hass, device_registry, "parent") is None

    # A discovery update with the same error keeps the current device
    caplog.clear()
    await _discover_switch(hass, "old", {**PARENT_DEVICE, "child_device": CHILD_DEVICE})
    assert REGISTRATION_WARNING in caplog.text
    old_entry = entity_registry.async_get("switch.old_switch")
    assert old_entry is not None
    assert old_entry.device_id == old_device.id
    assert _get_device(hass, device_registry, "parent") is None


async def test_device_registration_error(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a device using the identifiers of a child device."""
    await mqtt_mock_entry()
    await _discover_switch(hass, "sw1", {**PARENT_DEVICE, "child_device": CHILD_DEVICE})

    await _discover_switch(hass, "clash", CHILD_DEVICE, name="Clash")
    assert REGISTRATION_WARNING in caplog.text
    assert not [record for record in caplog.records if record.exc_info]
    entity_entry = entity_registry.async_get("switch.clash")
    assert entity_entry is not None
    assert entity_entry.device_id is None
    assert isinstance(
        _get_child_device(hass, device_registry, "sub"), dr.ChildDeviceEntry
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            DOMAIN: {
                "switch": [
                    {
                        "name": "Switch",
                        "command_topic": "sw1/set",
                        "unique_id": "sw1",
                        "device": {**PARENT_DEVICE, "child_device": CHILD_DEVICE},
                    },
                    {
                        "name": "Clash",
                        "command_topic": "clash/set",
                        "unique_id": "clash",
                        "device": CHILD_DEVICE,
                    },
                    {
                        "name": "After",
                        "command_topic": "after/set",
                        "unique_id": "after",
                        "device": {"identifiers": ["other"], "name": "Other"},
                    },
                ]
            }
        }
    ],
)
async def test_yaml_device_registration_error(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a device registration error does not block other YAML entities."""
    await mqtt_mock_entry()

    assert REGISTRATION_WARNING in caplog.text
    assert not [record for record in caplog.records if record.exc_info]
    clash_entry = entity_registry.async_get("switch.clash")
    assert clash_entry is not None
    assert clash_entry.device_id is None
    other = _get_device(hass, device_registry, "other")
    assert other is not None
    after_entry = entity_registry.async_get("switch.other_after")
    assert after_entry is not None
    assert after_entry.device_id == other.id


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            DOMAIN: {
                "switch": [
                    {
                        "name": "First",
                        "command_topic": "first/set",
                        "unique_id": "dup",
                        "device": {"identifiers": ["other"], "name": "Other"},
                    },
                    {
                        "name": "Duplicate",
                        "command_topic": "dup/set",
                        "unique_id": "dup",
                        "device": {**PARENT_DEVICE, "child_device": CHILD_DEVICE},
                    },
                    {
                        "name": "Between",
                        "command_topic": "between/set",
                        "state_topic": "between/state",
                        "unique_id": "between",
                    },
                    {
                        "name": "Later",
                        "command_topic": "later/set",
                        "unique_id": "later",
                        "device": {**PARENT_DEVICE, "child_device": CHILD_DEVICE},
                    },
                ]
            }
        }
    ],
)
async def test_yaml_rejected_duplicate_keeps_shared_child_device(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a rejected duplicate keeps a child device of a later YAML entity."""
    await mqtt_mock_entry()

    assert "ID dup already exists" in caplog.text
    child_device = _get_child_device(hass, device_registry, "sub")
    assert child_device is not None
    later_entry = entity_registry.async_get("switch.parent_sub_later")
    assert later_entry is not None
    assert later_entry.device_id == child_device.id


async def test_via_device_referencing_child_device(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a via device can not reference a child device."""
    await mqtt_mock_entry()
    await _discover_switch(hass, "sw1", {**PARENT_DEVICE, "child_device": CHILD_DEVICE})

    await _discover_switch(
        hass, "other", {"identifiers": ["other"], "name": "Other", "via_device": "sub"}
    )
    assert REGISTRATION_WARNING in caplog.text
    assert not [record for record in caplog.records if record.exc_info]
    other = _get_device(hass, device_registry, "other")
    assert other is not None
    assert other.via_device_id is None


@pytest.mark.parametrize(
    ("topic", "payload", "discovery_hash"),
    [
        pytest.param(
            TRIGGER_TOPIC,
            {**TRIGGER_CONFIG, "device": {"identifiers": ["sub"]}},
            ("device_automation", "trigger1"),
            id="device_trigger",
        ),
        pytest.param(
            TAG_TOPIC,
            {"topic": "tag1", "device": {"identifiers": ["sub"]}},
            ("tag", "tag1"),
            id="tag",
        ),
    ],
)
async def test_device_trigger_and_tag_registration_error(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    tag_mock: AsyncMock,
    caplog: pytest.LogCaptureFixture,
    topic: str,
    payload: dict[str, Any],
    discovery_hash: tuple[str, str],
) -> None:
    """Test the discovery is cancelled when the device can not be registered."""
    await mqtt_mock_entry()
    await _discover_switch(hass, "sw1", {**PARENT_DEVICE, "child_device": CHILD_DEVICE})

    async_fire_mqtt_message(hass, topic, json.dumps(payload))
    await hass.async_block_till_done()
    assert REGISTRATION_WARNING in caplog.text
    assert not [record for record in caplog.records if record.exc_info]
    mqtt_data = hass.data[DATA_MQTT]
    assert discovery_hash not in mqtt_data.discovery_already_discovered
    assert not mqtt_data.device_triggers

    # No tag scanner was set up
    async_fire_mqtt_message(hass, "tag1", "12345")
    await hass.async_block_till_done()
    tag_mock.assert_not_called()


async def test_device_trigger_update_registration_error(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a device trigger update is cancelled when the device can't be registered."""
    await mqtt_mock_entry()
    await _discover_switch(hass, "sw1", {**PARENT_DEVICE, "child_device": CHILD_DEVICE})
    payload = {**TRIGGER_CONFIG, "device": {"identifiers": ["trigger_device"]}}
    async_fire_mqtt_message(hass, TRIGGER_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()
    device = _get_device(hass, device_registry, "trigger_device")
    assert device is not None

    payload = {
        **TRIGGER_CONFIG,
        "subtype": "button_2",
        "device": {"identifiers": ["sub"]},
    }
    async_fire_mqtt_message(hass, TRIGGER_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()
    assert REGISTRATION_WARNING in caplog.text
    assert not [record for record in caplog.records if record.exc_info]
    # The trigger keeps its current config
    assert list(hass.data[DATA_MQTT].device_triggers) == [
        f"{device.id}_button_short_press_button_1"
    ]

    # An identical retry is processed again, and not ignored as an unchanged payload
    caplog.clear()
    async_fire_mqtt_message(hass, TRIGGER_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()
    assert REGISTRATION_WARNING in caplog.text


async def test_tag_update_registration_error(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    tag_mock: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a tag update is cancelled when the device can't be registered."""
    await mqtt_mock_entry()
    await _discover_switch(hass, "sw1", {**PARENT_DEVICE, "child_device": CHILD_DEVICE})
    payload = {"topic": "tag1", "device": {"identifiers": ["tag_device"]}}
    async_fire_mqtt_message(hass, TAG_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()

    payload = {"topic": "tag2", "device": {"identifiers": ["sub"]}}
    async_fire_mqtt_message(hass, TAG_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()
    assert REGISTRATION_WARNING in caplog.text
    assert not [record for record in caplog.records if record.exc_info]

    # The tag scanner keeps its current config
    async_fire_mqtt_message(hass, "tag2", "12345")
    await hass.async_block_till_done()
    tag_mock.assert_not_called()
    async_fire_mqtt_message(hass, "tag1", "12345")
    await hass.async_block_till_done()
    tag_mock.assert_called_once()
