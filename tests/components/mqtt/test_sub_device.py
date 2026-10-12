"""The tests for MQTT sub devices."""

import json
from typing import Any

import probatio
import pytest

from homeassistant.components.mqtt.const import DOMAIN
from homeassistant.components.mqtt.schemas import (
    MQTT_DEVICE_INFO_SCHEMA,
    MQTT_ENTITY_DEVICE_INFO_SCHEMA,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClientGenerator

PARENT_DEVICE = {"identifiers": ["parent"], "name": "Parent", "manufacturer": "Acme"}
SUB_DEVICE = {"identifiers": ["sub"], "name": "Sub"}
SWITCH_ENTITY_ID = "switch.parent_sub_switch"
SWITCH_TOPIC = "homeassistant/switch/sw1/config"
DEVICE_TOPIC = "homeassistant/device/parent/config"
REGISTRATION_WARNING = "Unable to register MQTT device"
UNIQUE_ID_REQUIRED = "'unique_id' is required when a 'sub_device' is configured"


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


def _get_sub_device(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, identifier: str
) -> dr.ChildDeviceEntry | None:
    """Return the sub device with the identifier."""
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


def test_sub_device_schema() -> None:
    """Test a valid sub device config."""
    assert MQTT_ENTITY_DEVICE_INFO_SCHEMA(
        {"identifiers": ["parent"], "sub_device": {"identifiers": "sub"}}
    )["sub_device"] == {"identifiers": ["sub"]}


@pytest.mark.parametrize(
    ("schema", "sub_device"),
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
def test_invalid_sub_device_schema(
    schema: probatio.All, sub_device: dict[str, Any]
) -> None:
    """Test an invalid sub device config."""
    with pytest.raises(probatio.Invalid):
        schema({"identifiers": ["parent"], "sub_device": sub_device})


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(
            _switch_config("sw1", {**PARENT_DEVICE, "sub_device": SUB_DEVICE}),
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
                        "sub_dev": {"ids": ["sub"], "name": "Sub"},
                    },
                }
            ),
            id="abbreviated",
        ),
    ],
)
async def test_single_component_discovery_with_sub_device(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    payload: str,
) -> None:
    """Test the entity is linked to the sub device of the parent device."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(hass, SWITCH_TOPIC, payload)
    await hass.async_block_till_done()

    parent = _get_device(hass, device_registry, "parent")
    assert parent is not None
    assert parent.name == "Parent"
    assert parent.manufacturer == "Acme"
    sub_device = _get_sub_device(hass, device_registry, "sub")
    assert sub_device is not None
    assert sub_device.name == "Sub"
    assert sub_device.parent_device_id == parent.id

    entity_entry = entity_registry.async_get(SWITCH_ENTITY_ID)
    assert entity_entry is not None
    assert entity_entry.device_id == sub_device.id


async def test_device_discovery_with_sub_device(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the sub device is set per component in device based discovery."""
    await mqtt_mock_entry()
    payload = {
        "dev": {"ids": ["parent"], "name": "Parent"},
        "o": {"name": "Foo2Mqtt"},
        "cmps": {
            "switch1": {
                "p": "switch",
                "name": "Switch",
                "cmd_t": "switch1/set",
                "uniq_id": "switch1",
                "sub_dev": {"ids": ["sub1"], "name": "Sub 1"},
            },
            "switch2": {
                "p": "switch",
                "name": "Switch",
                "cmd_t": "switch2/set",
                "uniq_id": "switch2",
                "sub_device": {"identifiers": ["sub2"], "name": "Sub 2"},
            },
            "rssi": {
                "p": "sensor",
                "name": "RSSI",
                "stat_t": "rssi",
                "uniq_id": "rssi",
            },
        },
    }
    async_fire_mqtt_message(hass, DEVICE_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()

    parent = _get_device(hass, device_registry, "parent")
    sub_device_1 = _get_sub_device(hass, device_registry, "sub1")
    sub_device_2 = _get_sub_device(hass, device_registry, "sub2")
    assert parent is not None
    assert sub_device_1 is not None
    assert sub_device_2 is not None
    assert sub_device_1.parent_device_id == parent.id
    assert sub_device_2.parent_device_id == parent.id

    switch_1 = entity_registry.async_get("switch.parent_sub_1_switch")
    switch_2 = entity_registry.async_get("switch.parent_sub_2_switch")
    rssi = entity_registry.async_get("sensor.parent_rssi")
    assert switch_1 is not None
    assert switch_2 is not None
    assert rssi is not None
    assert switch_1.device_id == sub_device_1.id
    assert switch_2.device_id == sub_device_2.id
    # The shared device config is not altered by the sub device of a component
    assert rssi.device_id == parent.id


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
                        "device": {**PARENT_DEVICE, "sub_device": SUB_DEVICE},
                    }
                ]
            }
        }
    ],
)
async def test_yaml_with_sub_device(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a manually configured entity on a sub device."""
    await mqtt_mock_entry()

    parent = _get_device(hass, device_registry, "parent")
    sub_device = _get_sub_device(hass, device_registry, "sub")
    assert parent is not None
    assert sub_device is not None
    assert sub_device.parent_device_id == parent.id
    entity_entry = entity_registry.async_get(SWITCH_ENTITY_ID)
    assert entity_entry is not None
    assert entity_entry.device_id == sub_device.id


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


async def test_discovery_sub_device_requires_unique_id(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a discovered sub device requires a unique ID."""
    await mqtt_mock_entry()
    payload = {
        "name": "Switch",
        "command_topic": "sw1/set",
        "device": {**PARENT_DEVICE, "sub_device": SUB_DEVICE},
    }
    async_fire_mqtt_message(hass, SWITCH_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()

    assert UNIQUE_ID_REQUIRED in caplog.text
    assert hass.states.get("switch.switch") is None
    assert not device_registry.devices


async def test_discovery_update_sub_device_requires_unique_id(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a discovery update adding a sub device requires a unique ID."""
    await mqtt_mock_entry()
    payload: dict[str, Any] = {"name": "Switch", "command_topic": "sw1/set"}
    async_fire_mqtt_message(hass, SWITCH_TOPIC, json.dumps(payload))
    await hass.async_block_till_done()
    assert hass.states.get("switch.switch") is not None

    payload["name"] = "Updated"
    payload["device"] = {**PARENT_DEVICE, "sub_device": SUB_DEVICE}
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
                        "device": {**PARENT_DEVICE, "sub_device": SUB_DEVICE},
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
async def test_yaml_sub_device_requires_unique_id(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a manually configured sub device requires a unique ID."""
    await mqtt_mock_entry()

    assert UNIQUE_ID_REQUIRED in caplog.text
    assert hass.states.get("switch.switch") is None
    assert hass.states.get("switch.other") is not None
    assert not device_registry.devices


async def test_sub_device_not_allowed_in_device_discovery_device(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a sub device is rejected in the shared device of device discovery."""
    await mqtt_mock_entry()
    payload = {
        "dev": {"ids": ["parent"], "name": "Parent", "sub_dev": {"ids": ["sub"]}},
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
    assert _get_sub_device(hass, device_registry, "sub") is None


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
                "dev": {"ids": ["parent"], "sub_dev": {"ids": ["sub"]}},
            },
            id="device_trigger",
        ),
        pytest.param(
            "homeassistant/tag/tag1/config",
            {
                "topic": "tag1",
                "dev": {"ids": ["parent"], "sub_dev": {"ids": ["sub"]}},
            },
            id="tag",
        ),
        pytest.param(
            DEVICE_TOPIC,
            {
                "dev": {"ids": ["parent"]},
                "o": {"name": "Foo2Mqtt"},
                "cmps": {
                    "trigger1": {
                        "p": "device_automation",
                        "automation_type": "trigger",
                        "topic": "button1",
                        "type": "button_short_press",
                        "subtype": "button_1",
                        "sub_dev": {"ids": ["sub"]},
                    },
                },
            },
            id="device_discovery_device_trigger",
        ),
        pytest.param(
            DEVICE_TOPIC,
            {
                "dev": {"ids": ["parent"]},
                "o": {"name": "Foo2Mqtt"},
                "cmps": {
                    "tag1": {"p": "tag", "topic": "tag1", "sub_dev": {"ids": ["sub"]}},
                },
            },
            id="device_discovery_tag",
        ),
    ],
)
@pytest.mark.usefixtures("tag_mock")
async def test_sub_device_not_supported_for_device_triggers_and_tags(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
    topic: str,
    payload: dict[str, Any],
) -> None:
    """Test device triggers and tags reject a sub device."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(hass, topic, json.dumps(payload))
    await hass.async_block_till_done()

    assert "not a valid option" in caplog.text
    assert "at 'device.sub_device'" in caplog.text
    assert _get_device(hass, device_registry, "parent") is None
    assert _get_sub_device(hass, device_registry, "sub") is None


async def test_discovery_update_sub_device(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a discovery update adds, changes and removes the sub device."""
    await mqtt_mock_entry()
    await _discover_switch(hass, "sw1", PARENT_DEVICE)
    parent = _get_device(hass, device_registry, "parent")
    assert parent is not None
    entity_id = "switch.parent_switch"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.device_id == parent.id

    # Add a sub device
    await _discover_switch(
        hass, "sw1", {**PARENT_DEVICE, "sub_device": {"identifiers": ["sub1"]}}
    )
    sub_device_1 = _get_sub_device(hass, device_registry, "sub1")
    assert sub_device_1 is not None
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.device_id == sub_device_1.id

    # Change the sub device, the old sub device is cleaned up
    await _discover_switch(
        hass, "sw1", {**PARENT_DEVICE, "sub_device": {"identifiers": ["sub2"]}}
    )
    sub_device_2 = _get_sub_device(hass, device_registry, "sub2")
    assert sub_device_2 is not None
    assert _get_sub_device(hass, device_registry, "sub1") is None
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.device_id == sub_device_2.id

    # Remove the sub device, the entity moves back to the parent device
    await _discover_switch(hass, "sw1", PARENT_DEVICE)
    assert _get_sub_device(hass, device_registry, "sub2") is None
    assert _get_device(hass, device_registry, "parent") == parent
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.device_id == parent.id


async def test_cleanup_parent_device_with_sub_device(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a parent device is kept while it has sub devices."""
    await mqtt_mock_entry()
    await _discover_switch(hass, "on_parent", PARENT_DEVICE)
    await _discover_switch(hass, "on_sub", {**PARENT_DEVICE, "sub_device": SUB_DEVICE})
    assert _get_device(hass, device_registry, "parent") is not None
    assert _get_sub_device(hass, device_registry, "sub") is not None

    # Removing the last entity of the parent device keeps the parent device,
    # as removing it would also remove its sub device
    async_fire_mqtt_message(hass, "homeassistant/switch/on_parent/config", "")
    await hass.async_block_till_done()
    assert _get_device(hass, device_registry, "parent") is not None
    assert _get_sub_device(hass, device_registry, "sub") is not None

    # Removing the last entity of the sub device also cleans up the parent device
    async_fire_mqtt_message(hass, "homeassistant/switch/on_sub/config", "")
    await hass.async_block_till_done()
    assert _get_sub_device(hass, device_registry, "sub") is None
    assert _get_device(hass, device_registry, "parent") is None


async def test_sub_device_registration_error(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a sub device that can not be registered.

    The identifiers of a device registered in this session can not be
    used for a sub device.
    """
    await mqtt_mock_entry()
    await _discover_switch(hass, "old", {"identifiers": ["sub"], "name": "Old"})
    old_device = _get_device(hass, device_registry, "sub")
    assert old_device is not None

    await _discover_switch(
        hass, "new", {**PARENT_DEVICE, "sub_device": SUB_DEVICE}, name="New"
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
    await _discover_switch(hass, "old", {**PARENT_DEVICE, "sub_device": SUB_DEVICE})
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
    """Test a device using the identifiers of a sub device."""
    await mqtt_mock_entry()
    await _discover_switch(hass, "sw1", {**PARENT_DEVICE, "sub_device": SUB_DEVICE})

    await _discover_switch(hass, "clash", SUB_DEVICE, name="Clash")
    assert REGISTRATION_WARNING in caplog.text
    assert not [record for record in caplog.records if record.exc_info]
    entity_entry = entity_registry.async_get("switch.clash")
    assert entity_entry is not None
    assert entity_entry.device_id is None
    assert isinstance(
        _get_sub_device(hass, device_registry, "sub"), dr.ChildDeviceEntry
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
                        "device": {**PARENT_DEVICE, "sub_device": SUB_DEVICE},
                    },
                    {
                        "name": "Clash",
                        "command_topic": "clash/set",
                        "unique_id": "clash",
                        "device": SUB_DEVICE,
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


async def test_via_device_referencing_sub_device(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a via device can not reference a sub device."""
    await mqtt_mock_entry()
    await _discover_switch(hass, "sw1", {**PARENT_DEVICE, "sub_device": SUB_DEVICE})

    await _discover_switch(
        hass, "other", {"identifiers": ["other"], "name": "Other", "via_device": "sub"}
    )
    assert REGISTRATION_WARNING in caplog.text
    assert not [record for record in caplog.records if record.exc_info]
    other = _get_device(hass, device_registry, "other")
    assert other is not None
    assert other.via_device_id is None


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
                "device": {"identifiers": ["sub"]},
            },
            id="device_trigger",
        ),
        pytest.param(
            "homeassistant/tag/tag1/config",
            {"topic": "tag1", "device": {"identifiers": ["sub"]}},
            id="tag",
        ),
    ],
)
@pytest.mark.usefixtures("tag_mock")
async def test_device_trigger_and_tag_registration_error(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    topic: str,
    payload: dict[str, Any],
) -> None:
    """Test a device trigger or tag device using the identifiers of a sub device."""
    await mqtt_mock_entry()
    await _discover_switch(hass, "sw1", {**PARENT_DEVICE, "sub_device": SUB_DEVICE})

    async_fire_mqtt_message(hass, topic, json.dumps(payload))
    await hass.async_block_till_done()
    assert REGISTRATION_WARNING in caplog.text
    assert not [record for record in caplog.records if record.exc_info]
