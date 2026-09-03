"""The tests for Z-Wave JS conditions."""

from typing import Any
from unittest.mock import MagicMock

import pytest
import voluptuous as vol
from zwave_js_server.const import CommandClass
from zwave_js_server.event import Event
from zwave_js_server.model.node import Node

from homeassistant.components.zwave_js import DOMAIN
from homeassistant.components.zwave_js.condition import CONDITIONS
from homeassistant.components.zwave_js.helpers import get_device_id
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    condition,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    label_registry as lr,
)
from homeassistant.helpers.translation import async_get_translations

from .common import COMMAND_CLASS_MARKERS, SCHLAGE_BE469_LOCK_ENTITY

from tests.common import MockConfigEntry


async def _checker(
    hass: HomeAssistant, config: dict[str, Any]
) -> condition.ConditionChecker:
    """Validate a condition config and build its checker."""
    validated = await condition.async_validate_condition_config(
        hass, cv.CONDITION_SCHEMA(config)
    )
    return await condition.async_from_config(hass, validated)


def _device_id(
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    node: Node,
    entry: MockConfigEntry,
) -> str:
    """Return the device registry ID for a node."""
    device = device_registry.async_get_device_by_identifier(
        get_device_id(client.driver, node), entry.entry_id
    )
    assert device
    return device.id


@pytest.mark.parametrize(
    ("condition_type", "options", "expected"),
    [
        pytest.param("node_status", {"status": "alive"}, True, id="node_status_match"),
        pytest.param(
            "node_status", {"status": "dead"}, False, id="node_status_mismatch"
        ),
        pytest.param(
            "config_parameter", {"parameter": 3, "value": 255}, True, id="param_raw"
        ),
        pytest.param(
            "config_parameter",
            {"parameter": 3, "value": "Enable Beeper"},
            True,
            id="param_label",
        ),
        pytest.param(
            "config_parameter", {"parameter": 3, "value": 0}, False, id="param_mismatch"
        ),
        pytest.param(
            "value",
            {"command_class": "98", "property": "currentMode", "value": "Unsecured"},
            True,
            id="value_label",
        ),
        pytest.param(
            "value",
            {"command_class": 98, "property": "currentMode", "value": 255},
            False,
            id="value_mismatch",
        ),
    ],
)
@pytest.mark.parametrize("target_kind", ["device", "entity"])
async def test_condition_by_device_and_entity(
    hass: HomeAssistant,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    condition_type: str,
    options: dict[str, Any],
    expected: bool,
    target_kind: str,
) -> None:
    """Test each condition targeted by device and by entity."""
    targets = {
        "device": {
            "device_id": _device_id(
                device_registry, client, lock_schlage_be469, integration
            )
        },
        "entity": {"entity_id": SCHLAGE_BE469_LOCK_ENTITY},
    }
    checker = await _checker(
        hass,
        {
            "condition": f"{DOMAIN}.{condition_type}",
            "target": targets[target_kind],
            "options": options,
        },
    )
    assert checker.async_check() is expected


@pytest.mark.parametrize(
    ("behavior", "target_kind", "expected"),
    [
        pytest.param("any", "two_nodes", True, id="any_one_alive"),
        pytest.param("all", "two_nodes", False, id="all_one_alive"),
        pytest.param("all", "same_node_twice", True, id="all_deduplicated_node"),
    ],
)
async def test_node_status_behavior(
    hass: HomeAssistant,
    client: MagicMock,
    lock_schlage_be469: Node,
    multisensor_6: Node,
    integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    behavior: str,
    target_kind: str,
    expected: bool,
) -> None:
    """Test any/all behavior, including that a node targeted twice is deduplicated."""
    lock_id = _device_id(device_registry, client, lock_schlage_be469, integration)
    targets = {
        "two_nodes": {
            "device_id": [
                lock_id,
                _device_id(device_registry, client, multisensor_6, integration),
            ]
        },
        "same_node_twice": {
            "device_id": [lock_id],
            "entity_id": [SCHLAGE_BE469_LOCK_ENTITY],
        },
    }
    checker = await _checker(
        hass,
        {
            "condition": f"{DOMAIN}.node_status",
            "target": targets[target_kind],
            "options": {"behavior": behavior, "status": "alive"},
        },
    )
    assert checker.async_check() is expected


async def test_node_status_follows_events(
    hass: HomeAssistant,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the node status condition reflects status changes."""
    checker = await _checker(
        hass,
        {
            "condition": f"{DOMAIN}.node_status",
            "target": {
                "device_id": _device_id(
                    device_registry, client, lock_schlage_be469, integration
                )
            },
            "options": {"status": "dead"},
        },
    )
    assert checker.async_check() is False
    lock_schlage_be469.receive_event(
        Event(
            "dead",
            data={
                "source": "node",
                "event": "dead",
                "nodeId": lock_schlage_be469.node_id,
            },
        )
    )
    assert checker.async_check() is True


async def test_node_status_all_two_nodes_match(
    hass: HomeAssistant,
    client: MagicMock,
    lock_schlage_be469: Node,
    multisensor_6: Node,
    integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test an all behavior only matches once every targeted node matches."""
    checker = await _checker(
        hass,
        {
            "condition": f"{DOMAIN}.node_status",
            "target": {
                "device_id": [
                    _device_id(
                        device_registry, client, lock_schlage_be469, integration
                    ),
                    _device_id(device_registry, client, multisensor_6, integration),
                ]
            },
            "options": {"behavior": "all", "status": "alive"},
        },
    )
    assert checker.async_check() is False
    multisensor_6.receive_event(
        Event(
            "alive",
            data={
                "source": "node",
                "event": "alive",
                "nodeId": multisensor_6.node_id,
            },
        )
    )
    assert checker.async_check() is True


async def test_target_by_label(
    hass: HomeAssistant,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """Test a label target resolves to the labelled device."""
    device_id = _device_id(device_registry, client, lock_schlage_be469, integration)
    label = label_registry.async_create("locks")
    device_registry.async_update_device(device_id, labels={label.label_id})
    checker = await _checker(
        hass,
        {
            "condition": f"{DOMAIN}.node_status",
            "target": {"label_id": label.label_id},
            "options": {"status": "alive"},
        },
    )
    assert checker.async_check() is True


async def test_value_missing_on_node(
    hass: HomeAssistant,
    client: MagicMock,
    lock_schlage_be469: Node,
    multisensor_6: Node,
    integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a node without the value does not match and validation needs one node with it."""
    lock_id = _device_id(device_registry, client, lock_schlage_be469, integration)
    sensor_id = _device_id(device_registry, client, multisensor_6, integration)
    options = {"command_class": 98, "property": "currentMode", "value": 0}

    checker = await _checker(
        hass,
        {
            "condition": f"{DOMAIN}.value",
            "target": {"device_id": [lock_id, sensor_id]},
            "options": {**options, "behavior": "all"},
        },
    )
    assert checker.async_check() is False

    with pytest.raises(vol.Invalid, match="No node in the target has value"):
        await _checker(
            hass,
            {
                "condition": f"{DOMAIN}.value",
                "target": {"device_id": sensor_id},
                "options": options,
            },
        )


async def test_value_property_key_zero(
    hass: HomeAssistant,
    client: MagicMock,
    bulb_6_multi_color: Node,
    integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a property key of 0 is not treated as an absent property key."""
    checker = await _checker(
        hass,
        {
            "condition": f"{DOMAIN}.value",
            "target": {
                "device_id": _device_id(
                    device_registry, client, bulb_6_multi_color, integration
                )
            },
            "options": {
                "command_class": 51,
                "property": "currentColor",
                "property_key": 0,
                "value": 255,
            },
        },
    )
    assert checker.async_check() is True


async def test_no_nodes_resolved(
    hass: HomeAssistant,
    integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test validation rejects a target that resolves to no Z-Wave nodes."""
    other = device_registry.async_get_or_create(
        config_entry_id=integration.entry_id, identifiers={("other", "1")}
    )
    with pytest.raises(vol.Invalid, match="No nodes found"):
        await _checker(
            hass,
            {
                "condition": f"{DOMAIN}.node_status",
                "target": {"device_id": other.id},
                "options": {"status": "alive"},
            },
        )


async def test_validation_bypassed_when_not_loaded(
    hass: HomeAssistant,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test dynamic validation is skipped while the config entry is not loaded."""
    device_id = _device_id(device_registry, client, lock_schlage_be469, integration)
    await hass.config_entries.async_unload(integration.entry_id)
    validated = await condition.async_validate_condition_config(
        hass,
        cv.CONDITION_SCHEMA(
            {
                "condition": f"{DOMAIN}.value",
                "target": {"device_id": device_id},
                "options": {"command_class": 98, "property": "nope", "value": 0},
            }
        ),
    )
    assert validated["options"]["property"] == "nope"


async def test_config_parameter_with_bitmask(
    hass: HomeAssistant,
    client: MagicMock,
    multisensor_6: Node,
    integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a config parameter condition with a partial parameter bitmask."""
    checker = await _checker(
        hass,
        {
            "condition": f"{DOMAIN}.config_parameter",
            "target": {
                "device_id": _device_id(
                    device_registry, client, multisensor_6, integration
                )
            },
            "options": {"parameter": 101, "bitmask": "0x1", "value": 1},
        },
    )
    assert checker.async_check() is True


async def test_top_level_fields_moved_to_options(
    hass: HomeAssistant,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test top level option fields are moved into the options block."""
    validated = await condition.async_validate_condition_config(
        hass,
        cv.CONDITION_SCHEMA(
            {
                "condition": f"{DOMAIN}.node_status",
                "target": {
                    "device_id": _device_id(
                        device_registry, client, lock_schlage_be469, integration
                    )
                },
                "status": "alive",
                "behavior": "all",
            }
        ),
    )
    assert validated["options"] == {"behavior": "all", "status": "alive"}
    assert "status" not in validated


async def test_target_by_area(
    hass: HomeAssistant,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    area_registry: ar.AreaRegistry,
) -> None:
    """Test an area target resolves to the devices in that area."""
    device_id = _device_id(device_registry, client, lock_schlage_be469, integration)
    area = area_registry.async_create("basement")
    device_registry.async_update_device(device_id, area_id=area.id)
    checker = await _checker(
        hass,
        {
            "condition": f"{DOMAIN}.node_status",
            "target": {"area_id": area.id},
            "options": {"status": "alive"},
        },
    )
    assert checker.async_check() is True


@pytest.mark.usefixtures("client", "lock_schlage_be469", "integration")
async def test_non_zwave_entity_is_skipped(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entities from other integrations in the target are ignored."""
    other_entry = MockConfigEntry(domain="other")
    other_entry.add_to_hass(hass)
    other_device = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id, identifiers={("other", "dev")}
    )
    other = entity_registry.async_get_or_create(
        "sensor", "other", "1", device_id=other_device.id
    )
    checker = await _checker(
        hass,
        {
            "condition": f"{DOMAIN}.node_status",
            "target": {"entity_id": [SCHLAGE_BE469_LOCK_ENTITY, other.entity_id]},
            "options": {"status": "alive"},
        },
    )
    assert checker.async_check() is True


async def test_check_false_when_nodes_disappear(
    hass: HomeAssistant,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the condition is False once the target no longer resolves to nodes."""
    checker = await _checker(
        hass,
        {
            "condition": f"{DOMAIN}.node_status",
            "target": {
                "device_id": _device_id(
                    device_registry, client, lock_schlage_be469, integration
                )
            },
            "options": {"status": "alive"},
        },
    )
    assert checker.async_check() is True
    await hass.config_entries.async_unload(integration.entry_id)
    assert checker.async_check() is False


@pytest.mark.parametrize(
    ("behavior", "expected"),
    [("any", True), ("all", False)],
)
async def test_partially_unresolved_target(
    hass: HomeAssistant,
    client: MagicMock,
    lock_schlage_be469: Node,
    multisensor_6: Node,
    integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    behavior: str,
    expected: bool,
) -> None:
    """Test a targeted Z-Wave node that cannot be resolved fails an all behavior."""
    target = {
        "device_id": [
            _device_id(device_registry, client, lock_schlage_be469, integration),
            _device_id(device_registry, client, multisensor_6, integration),
        ]
    }
    del client.driver.controller.nodes[multisensor_6.node_id]
    checker = await _checker(
        hass,
        {
            "condition": f"{DOMAIN}.node_status",
            "target": target,
            "options": {"behavior": behavior, "status": "alive"},
        },
    )
    assert checker.async_check() is expected


async def test_config_parameter_missing_on_node(
    hass: HomeAssistant,
    client: MagicMock,
    lock_schlage_be469: Node,
    integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test validation fails when no node in the target has the parameter."""
    device_id = _device_id(device_registry, client, lock_schlage_be469, integration)
    with pytest.raises(vol.Invalid, match="configuration parameter"):
        await _checker(
            hass,
            {
                "condition": f"{DOMAIN}.config_parameter",
                "target": {"device_id": device_id},
                "options": {"parameter": 9999, "value": 1},
            },
        )


@pytest.mark.parametrize("condition_type", list(CONDITIONS), ids=list(CONDITIONS))
@pytest.mark.usefixtures("integration")
async def test_condition_description_fields_match_schema(
    hass: HomeAssistant, condition_type: str
) -> None:
    """Test the described fields and required flags match the options schema."""
    schema = CONDITIONS[condition_type].options_schema_dict
    descriptions = await condition.async_get_all_descriptions(hass)
    fields = descriptions[f"{DOMAIN}.{condition_type}"]["fields"]
    assert set(fields) == {str(key) for key in schema}
    assert {name for name, field in fields.items() if field["required"]} == {
        str(key) for key in schema if isinstance(key, vol.Required)
    }


@pytest.mark.usefixtures("integration")
async def test_value_command_class_options(hass: HomeAssistant) -> None:
    """Test the value condition's command class options match the CommandClass enum."""
    expected = {str(cc.value) for cc in CommandClass if cc not in COMMAND_CLASS_MARKERS}
    descriptions = await condition.async_get_all_descriptions(hass)
    options = descriptions[f"{DOMAIN}.value"]["fields"]["command_class"]["selector"][
        "select"
    ]["options"]
    assert len(options) == len(expected)
    assert set(options) == expected


@pytest.mark.usefixtures("integration")
async def test_node_status_selector_translations(hass: HomeAssistant) -> None:
    """Test the node status selector options are translated."""
    translations = await async_get_translations(hass, "en", "selector", {DOMAIN})
    prefix = f"component.{DOMAIN}.selector.node_status.options."
    assert {
        key.removeprefix(prefix) for key in translations if key.startswith(prefix)
    } == {"alive", "asleep", "awake", "dead"}
