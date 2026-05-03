"""Tests for the ISY994 device triggers."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.isy994.const import DOMAIN, EVENT_ISY994_CONTROL
from homeassistant.components.isy994.device_trigger import CONF_SUBTYPE, TRIGGER_TYPES
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import MOCK_UUID

from tests.common import MockConfigEntry, async_get_device_automations

ROOT_ADDRESS = "11 22 33 1"
ROOT_UNIQUE_ID = f"{MOCK_UUID}_{ROOT_ADDRESS}"


def _make_node(address: str, name: str, node_def_id: str | None) -> MagicMock:
    node = MagicMock()
    node.address = address
    node.name = name
    node.node_def_id = node_def_id
    return node


def _wire_runtime(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isy: MagicMock,
    nodes_by_addr: dict[str, MagicMock],
) -> dr.DeviceEntry:
    """Set up runtime_data + a single device entry covering all given nodes."""
    mock_config_entry.add_to_hass(hass)

    mock_isy.nodes.get_by_id = MagicMock(side_effect=nodes_by_addr.get)

    runtime_data = MagicMock()
    runtime_data.root = mock_isy
    runtime_data.uuid = MOCK_UUID
    runtime_data.devices = {ROOT_ADDRESS: MagicMock()}
    mock_config_entry.runtime_data = runtime_data
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)

    return dr.async_get(hass).async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, ROOT_UNIQUE_ID)},
        name="Test Insteon Device",
    )


def _register_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device: dr.DeviceEntry,
    *,
    domain: str,
    address: str,
    object_id: str,
) -> str:
    entry = er.async_get(hass).async_get_or_create(
        domain=domain,
        platform=DOMAIN,
        unique_id=f"{MOCK_UUID}_{address}",
        config_entry=mock_config_entry,
        device_id=device.id,
        suggested_object_id=object_id,
    )
    return entry.entity_id


async def test_get_triggers_dimmer_switch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isy: MagicMock,
) -> None:
    """A SwitchLinc dimmer exposes one trigger per type."""
    nodes = {
        ROOT_ADDRESS: _make_node(ROOT_ADDRESS, "Office Dimmer", "DimmerSwitchOnly_ADV")
    }
    device = _wire_runtime(hass, mock_config_entry, mock_isy, nodes)
    entity_id = _register_entity(
        hass,
        mock_config_entry,
        device,
        domain="light",
        address=ROOT_ADDRESS,
        object_id="office_dimmer",
    )

    triggers = [
        t
        for t in await async_get_device_automations(
            hass, DeviceAutomationType.TRIGGER, device.id
        )
        if t.get(CONF_DOMAIN) == DOMAIN
    ]

    assert {t[CONF_TYPE] for t in triggers} == set(TRIGGER_TYPES)
    assert all(t[CONF_SUBTYPE] == ROOT_ADDRESS for t in triggers)
    assert all(t[CONF_DEVICE_ID] == device.id for t in triggers)
    assert all(t["entity_id"] == entity_id for t in triggers)


async def test_get_triggers_keypad_dimmer_with_buttons(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isy: MagicMock,
) -> None:
    """A KPL dimmer exposes triggers for the load and each secondary button."""
    button_b_addr = "11 22 33 2"
    button_c_addr = "11 22 33 3"
    nodes = {
        ROOT_ADDRESS: _make_node(ROOT_ADDRESS, "KPL Load", "KeypadDimmer_ADV"),
        button_b_addr: _make_node(button_b_addr, "KPL B", "KeypadButton_ADV"),
        button_c_addr: _make_node(button_c_addr, "KPL C", "KeypadButton_ADV"),
    }
    device = _wire_runtime(hass, mock_config_entry, mock_isy, nodes)
    load_entity = _register_entity(
        hass,
        mock_config_entry,
        device,
        domain="light",
        address=ROOT_ADDRESS,
        object_id="kpl_load",
    )
    button_b_entity = _register_entity(
        hass,
        mock_config_entry,
        device,
        domain="switch",
        address=button_b_addr,
        object_id="kpl_b",
    )
    button_c_entity = _register_entity(
        hass,
        mock_config_entry,
        device,
        domain="switch",
        address=button_c_addr,
        object_id="kpl_c",
    )

    triggers = [
        t
        for t in await async_get_device_automations(
            hass, DeviceAutomationType.TRIGGER, device.id
        )
        if t.get(CONF_DOMAIN) == DOMAIN
    ]

    by_subtype: dict[str, set[str]] = {}
    entity_by_subtype: dict[str, set[str]] = {}
    for t in triggers:
        by_subtype.setdefault(t[CONF_SUBTYPE], set()).add(t[CONF_TYPE])
        entity_by_subtype.setdefault(t[CONF_SUBTYPE], set()).add(t["entity_id"])
    assert by_subtype == {
        ROOT_ADDRESS: set(TRIGGER_TYPES),
        button_b_addr: set(TRIGGER_TYPES),
        button_c_addr: set(TRIGGER_TYPES),
    }
    assert entity_by_subtype == {
        ROOT_ADDRESS: {load_entity},
        button_b_addr: {button_b_entity},
        button_c_addr: {button_c_entity},
    }


async def test_get_triggers_unsupported_node_def_returns_empty(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isy: MagicMock,
) -> None:
    """Nodes whose node_def_id is not in the supported set yield no triggers."""
    nodes = {
        ROOT_ADDRESS: _make_node(ROOT_ADDRESS, "Motion Sensor", "MotionSensor_ADV"),
    }
    device = _wire_runtime(hass, mock_config_entry, mock_isy, nodes)
    _register_entity(
        hass,
        mock_config_entry,
        device,
        domain="binary_sensor",
        address=ROOT_ADDRESS,
        object_id="motion",
    )

    triggers = [
        t
        for t in await async_get_device_automations(
            hass, DeviceAutomationType.TRIGGER, device.id
        )
        if t.get(CONF_DOMAIN) == DOMAIN
    ]
    assert triggers == []


@pytest.mark.parametrize(
    ("trigger_type", "control_code", "should_fire"),
    [
        ("on_fast", "DFON", True),
        ("on_fast", "DON", False),
        ("on", "DON", True),
        ("fade_up", "FDUP", True),
        ("fade_stop", "FDSTOP", True),
        ("fade_stop", "FDUP", False),
    ],
)
async def test_trigger_fires_on_matching_control(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isy: MagicMock,
    trigger_type: str,
    control_code: str,
    should_fire: bool,
) -> None:
    """A configured trigger fires only on matching entity_id + control code."""
    nodes = {
        ROOT_ADDRESS: _make_node(
            ROOT_ADDRESS, "Bedroom Dimmer", "DimmerSwitchOnly_ADV"
        ),
    }
    device = _wire_runtime(hass, mock_config_entry, mock_isy, nodes)
    entity_id = _register_entity(
        hass,
        mock_config_entry,
        device,
        domain="light",
        address=ROOT_ADDRESS,
        object_id="bedroom_dimmer",
    )

    calls: list[ServiceCall] = []

    async def _capture(call: ServiceCall) -> None:
        calls.append(call)

    hass.services.async_register("test", "automation", _capture)

    assert await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: [
                {
                    "alias": "t",
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: device.id,
                        CONF_TYPE: trigger_type,
                        CONF_SUBTYPE: ROOT_ADDRESS,
                    },
                    "action": {"service": "test.automation"},
                }
            ]
        },
    )
    await hass.async_block_till_done()

    hass.bus.async_fire(
        EVENT_ISY994_CONTROL,
        {"entity_id": entity_id, "control": control_code},
    )
    await hass.async_block_till_done()

    assert len(calls) == (1 if should_fire else 0)


async def test_trigger_isolated_per_button(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isy: MagicMock,
) -> None:
    """A trigger bound to KPL button B does not fire when button C is pressed."""
    button_b_addr = "11 22 33 2"
    button_c_addr = "11 22 33 3"
    nodes = {
        ROOT_ADDRESS: _make_node(ROOT_ADDRESS, "KPL Load", "KeypadDimmer_ADV"),
        button_b_addr: _make_node(button_b_addr, "KPL B", "KeypadButton_ADV"),
        button_c_addr: _make_node(button_c_addr, "KPL C", "KeypadButton_ADV"),
    }
    device = _wire_runtime(hass, mock_config_entry, mock_isy, nodes)
    _register_entity(
        hass,
        mock_config_entry,
        device,
        domain="light",
        address=ROOT_ADDRESS,
        object_id="kpl_load",
    )
    button_b_entity = _register_entity(
        hass,
        mock_config_entry,
        device,
        domain="switch",
        address=button_b_addr,
        object_id="kpl_b",
    )
    button_c_entity = _register_entity(
        hass,
        mock_config_entry,
        device,
        domain="switch",
        address=button_c_addr,
        object_id="kpl_c",
    )

    calls: list[ServiceCall] = []

    async def _capture(call: ServiceCall) -> None:
        calls.append(call)

    hass.services.async_register("test", "automation", _capture)

    assert await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: [
                {
                    "alias": "t",
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: device.id,
                        CONF_TYPE: "on_fast",
                        CONF_SUBTYPE: button_b_addr,
                    },
                    "action": {"service": "test.automation"},
                }
            ]
        },
    )
    await hass.async_block_till_done()

    hass.bus.async_fire(
        EVENT_ISY994_CONTROL,
        {"entity_id": button_c_entity, "control": "DFON"},
    )
    await hass.async_block_till_done()
    assert calls == []

    hass.bus.async_fire(
        EVENT_ISY994_CONTROL,
        {"entity_id": button_b_entity, "control": "DFON"},
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
