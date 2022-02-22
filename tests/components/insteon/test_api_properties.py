"""Test the Insteon properties APIs."""

import json
from unittest.mock import patch

import pytest

from homeassistant.components import insteon
from homeassistant.components.insteon.api import async_load_api
from homeassistant.components.insteon.api.device import INSTEON_DEVICE_NOT_FOUND
from homeassistant.components.insteon.api.properties import (
    DEVICE_ADDRESS,
    ID,
    NON_TOGGLE_MASK,
    NON_TOGGLE_OFF_MODE,
    NON_TOGGLE_ON_MODE,
    NON_TOGGLE_ON_OFF_MASK,
    PROPERTY_NAME,
    PROPERTY_VALUE,
    RADIO_BUTTON_GROUP_PROP,
    TOGGLE_MODES,
    TOGGLE_ON_OFF_MODE,
    TOGGLE_PROP,
    TYPE,
    _get_radio_button_properties,
    _get_toggle_properties,
)

from .mock_devices import MockDevices

from tests.common import load_fixture


@pytest.fixture(name="properties_data", scope="session")
def aldb_data_fixture():
    """Load the controller state fixture data."""
    return json.loads(load_fixture("insteon/kpl_properties.json"))


async def _setup(hass, hass_ws_client, properties_data):
    """Set up tests."""
    ws_client = await hass_ws_client(hass)
    devices = MockDevices()
    await devices.async_load()
    devices.fill_properties("33.33.33", properties_data)
    async_load_api(hass)
    return ws_client, devices


async def test_get_properties(hass, hass_ws_client, properties_data):
    """Test getting an Insteon device's properties."""
    ws_client, devices = await _setup(hass, hass_ws_client, properties_data)

    with patch.object(insteon.api.properties, "devices", devices):
        await ws_client.send_json(
            {ID: 2, TYPE: "insteon/properties/get", DEVICE_ADDRESS: "33.33.33"}
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert len(msg["result"]["properties"]) == 54


async def test_change_operating_flag(hass, hass_ws_client, properties_data):
    """Test changing an Insteon device's properties."""
    ws_client, devices = await _setup(hass, hass_ws_client, properties_data)

    with patch.object(insteon.api.properties, "devices", devices):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "insteon/properties/change",
                DEVICE_ADDRESS: "33.33.33",
                PROPERTY_NAME: "led_off",
                PROPERTY_VALUE: True,
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert devices["33.33.33"].operating_flags["led_off"].is_dirty


async def test_change_property(hass, hass_ws_client, properties_data):
    """Test changing an Insteon device's properties."""
    ws_client, devices = await _setup(hass, hass_ws_client, properties_data)

    with patch.object(insteon.api.properties, "devices", devices):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "insteon/properties/change",
                DEVICE_ADDRESS: "33.33.33",
                PROPERTY_NAME: "on_mask",
                PROPERTY_VALUE: 100,
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert devices["33.33.33"].properties["on_mask"].new_value == 100
        assert devices["33.33.33"].properties["on_mask"].is_dirty


async def test_change_ramp_rate_property(hass, hass_ws_client, properties_data):
    """Test changing an Insteon device's properties."""
    ws_client, devices = await _setup(hass, hass_ws_client, properties_data)

    with patch.object(insteon.api.properties, "devices", devices):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "insteon/properties/change",
                DEVICE_ADDRESS: "33.33.33",
                PROPERTY_NAME: "ramp_rate",
                PROPERTY_VALUE: 4.5,
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert devices["33.33.33"].properties["ramp_rate"].new_value == 0x1A
        assert devices["33.33.33"].properties["ramp_rate"].is_dirty


async def test_change_radio_button_group(hass, hass_ws_client, properties_data):
    """Test changing an Insteon device's properties."""
    ws_client, devices = await _setup(hass, hass_ws_client, properties_data)
    rb_props, schema = _get_radio_button_properties(devices["33.33.33"])

    # Make sure the baseline is correct
    assert rb_props[0]["name"] == f"{RADIO_BUTTON_GROUP_PROP}0"
    assert rb_props[0]["value"] == [4, 5]
    assert rb_props[1]["value"] == [7, 8]
    assert rb_props[2]["value"] == []
    assert schema[f"{RADIO_BUTTON_GROUP_PROP}0"]["options"].get(1)
    assert schema[f"{RADIO_BUTTON_GROUP_PROP}1"]["options"].get(1)
    assert devices["33.33.33"].properties["on_mask"].value == 0
    assert devices["33.33.33"].properties["off_mask"].value == 0
    assert not devices["33.33.33"].properties["on_mask"].is_dirty
    assert not devices["33.33.33"].properties["off_mask"].is_dirty

    # Add button 1 to the group
    rb_props[0]["value"].append(1)
    with patch.object(insteon.api.properties, "devices", devices):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "insteon/properties/change",
                DEVICE_ADDRESS: "33.33.33",
                PROPERTY_NAME: f"{RADIO_BUTTON_GROUP_PROP}0",
                PROPERTY_VALUE: rb_props[0]["value"],
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]

        new_rb_props, _ = _get_radio_button_properties(devices["33.33.33"])
        assert 1 in new_rb_props[0]["value"]
        assert 4 in new_rb_props[0]["value"]
        assert 5 in new_rb_props[0]["value"]
        assert schema[f"{RADIO_BUTTON_GROUP_PROP}0"]["options"].get(1)
        assert schema[f"{RADIO_BUTTON_GROUP_PROP}1"]["options"].get(1)

        assert devices["33.33.33"].properties["on_mask"].new_value == 0x18
        assert devices["33.33.33"].properties["off_mask"].new_value == 0x18
        assert devices["33.33.33"].properties["on_mask"].is_dirty
        assert devices["33.33.33"].properties["off_mask"].is_dirty

        # Remove button 5
        rb_props[0]["value"].remove(5)
        await ws_client.send_json(
            {
                ID: 3,
                TYPE: "insteon/properties/change",
                DEVICE_ADDRESS: "33.33.33",
                PROPERTY_NAME: f"{RADIO_BUTTON_GROUP_PROP}0",
                PROPERTY_VALUE: rb_props[0]["value"],
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]

        new_rb_props, _ = _get_radio_button_properties(devices["33.33.33"])
        assert 1 in new_rb_props[0]["value"]
        assert 4 in new_rb_props[0]["value"]
        assert 5 not in new_rb_props[0]["value"]
        assert schema[f"{RADIO_BUTTON_GROUP_PROP}0"]["options"].get(1)
        assert schema[f"{RADIO_BUTTON_GROUP_PROP}1"]["options"].get(1)

        assert devices["33.33.33"].properties["on_mask"].new_value == 0x08
        assert devices["33.33.33"].properties["off_mask"].new_value == 0x08
        assert devices["33.33.33"].properties["on_mask"].is_dirty
        assert devices["33.33.33"].properties["off_mask"].is_dirty

        # Remove button group 1
        rb_props[1]["value"] = []
        await ws_client.send_json(
            {
                ID: 5,
                TYPE: "insteon/properties/change",
                DEVICE_ADDRESS: "33.33.33",
                PROPERTY_NAME: f"{RADIO_BUTTON_GROUP_PROP}1",
                PROPERTY_VALUE: rb_props[1]["value"],
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]

        new_rb_props, _ = _get_radio_button_properties(devices["33.33.33"])
        assert len(new_rb_props) == 2
        assert new_rb_props[0]["value"] == [1, 4]
        assert new_rb_props[1]["value"] == []


async def test_create_radio_button_group(hass, hass_ws_client, properties_data):
    """Test changing an Insteon device's properties."""
    ws_client, devices = await _setup(hass, hass_ws_client, properties_data)
    rb_props, _ = _get_radio_button_properties(devices["33.33.33"])

    # Make sure the baseline is correct
    assert len(rb_props) == 3

    rb_props[0]["value"].append("1")

    with patch.object(insteon.api.properties, "devices", devices):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "insteon/properties/change",
                DEVICE_ADDRESS: "33.33.33",
                PROPERTY_NAME: f"{RADIO_BUTTON_GROUP_PROP}2",
                PROPERTY_VALUE: ["1", "3"],
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]

        new_rb_props, new_schema = _get_radio_button_properties(devices["33.33.33"])
        assert len(new_rb_props) == 4
        assert 1 in new_rb_props[0]["value"]
        assert new_schema[f"{RADIO_BUTTON_GROUP_PROP}0"]["options"].get(1)
        assert not new_schema[f"{RADIO_BUTTON_GROUP_PROP}1"]["options"].get(1)

        assert devices["33.33.33"].properties["on_mask"].new_value == 4
        assert devices["33.33.33"].properties["off_mask"].new_value == 4
        assert devices["33.33.33"].properties["on_mask"].is_dirty
        assert devices["33.33.33"].properties["off_mask"].is_dirty


async def test_change_toggle_property(hass, hass_ws_client, properties_data):
    """Update a button's toggle mode."""
    ws_client, devices = await _setup(hass, hass_ws_client, properties_data)
    device = devices["33.33.33"]
    toggle_props, _ = _get_toggle_properties(devices["33.33.33"])

    # Make sure the baseline is correct
    assert toggle_props[0]["name"] == f"{TOGGLE_PROP}{device.groups[1].name}"
    assert toggle_props[0]["value"] == TOGGLE_MODES[TOGGLE_ON_OFF_MODE]
    assert toggle_props[1]["value"] == TOGGLE_MODES[NON_TOGGLE_ON_MODE]
    assert device.properties[NON_TOGGLE_MASK].value == 2
    assert device.properties[NON_TOGGLE_ON_OFF_MASK].value == 2
    assert not device.properties[NON_TOGGLE_MASK].is_dirty
    assert not device.properties[NON_TOGGLE_ON_OFF_MASK].is_dirty

    with patch.object(insteon.api.properties, "devices", devices):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "insteon/properties/change",
                DEVICE_ADDRESS: "33.33.33",
                PROPERTY_NAME: toggle_props[0]["name"],
                PROPERTY_VALUE: 1,
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]

        new_toggle_props, _ = _get_toggle_properties(devices["33.33.33"])
        assert new_toggle_props[0]["value"] == TOGGLE_MODES[NON_TOGGLE_ON_MODE]
        assert device.properties[NON_TOGGLE_MASK].new_value == 3
        assert device.properties[NON_TOGGLE_ON_OFF_MASK].new_value == 3
        assert device.properties[NON_TOGGLE_MASK].is_dirty
        assert device.properties[NON_TOGGLE_ON_OFF_MASK].is_dirty

        await ws_client.send_json(
            {
                ID: 3,
                TYPE: "insteon/properties/change",
                DEVICE_ADDRESS: "33.33.33",
                PROPERTY_NAME: toggle_props[0]["name"],
                PROPERTY_VALUE: 2,
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]

        new_toggle_props, _ = _get_toggle_properties(devices["33.33.33"])
        assert new_toggle_props[0]["value"] == TOGGLE_MODES[NON_TOGGLE_OFF_MODE]
        assert device.properties[NON_TOGGLE_MASK].new_value == 3
        assert device.properties[NON_TOGGLE_ON_OFF_MASK].new_value is None
        assert device.properties[NON_TOGGLE_MASK].is_dirty
        assert not device.properties[NON_TOGGLE_ON_OFF_MASK].is_dirty

        await ws_client.send_json(
            {
                ID: 4,
                TYPE: "insteon/properties/change",
                DEVICE_ADDRESS: "33.33.33",
                PROPERTY_NAME: toggle_props[1]["name"],
                PROPERTY_VALUE: 0,
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]

        new_toggle_props, _ = _get_toggle_properties(devices["33.33.33"])
        assert new_toggle_props[1]["value"] == TOGGLE_MODES[TOGGLE_ON_OFF_MODE]
        assert device.properties[NON_TOGGLE_MASK].new_value == 1
        assert device.properties[NON_TOGGLE_ON_OFF_MASK].new_value == 0
        assert device.properties[NON_TOGGLE_MASK].is_dirty
        assert device.properties[NON_TOGGLE_ON_OFF_MASK].is_dirty


async def test_write_properties(hass, hass_ws_client, properties_data):
    """Test getting an Insteon device's properties."""
    ws_client, devices = await _setup(hass, hass_ws_client, properties_data)

    with patch.object(insteon.api.properties, "devices", devices):
        await ws_client.send_json(
            {ID: 2, TYPE: "insteon/properties/write", DEVICE_ADDRESS: "33.33.33"}
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert devices["33.33.33"].async_write_op_flags.call_count == 1
        assert devices["33.33.33"].async_write_ext_properties.call_count == 1


async def test_write_properties_failure(hass, hass_ws_client, properties_data):
    """Test getting an Insteon device's properties."""
    ws_client, devices = await _setup(hass, hass_ws_client, properties_data)

    with patch.object(insteon.api.properties, "devices", devices):
        await ws_client.send_json(
            {ID: 2, TYPE: "insteon/properties/write", DEVICE_ADDRESS: "22.22.22"}
        )
        msg = await ws_client.receive_json()
        assert not msg["success"]
        assert msg["error"]["code"] == "write_failed"


async def test_load_properties(hass, hass_ws_client, properties_data):
    """Test getting an Insteon device's properties."""
    ws_client, devices = await _setup(hass, hass_ws_client, properties_data)

    with patch.object(insteon.api.properties, "devices", devices):
        await ws_client.send_json(
            {ID: 2, TYPE: "insteon/properties/load", DEVICE_ADDRESS: "33.33.33"}
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert devices["33.33.33"].async_read_op_flags.call_count == 1
        assert devices["33.33.33"].async_read_ext_properties.call_count == 1


async def test_load_properties_failure(hass, hass_ws_client, properties_data):
    """Test getting an Insteon device's properties."""
    ws_client, devices = await _setup(hass, hass_ws_client, properties_data)

    with patch.object(insteon.api.properties, "devices", devices):
        await ws_client.send_json(
            {ID: 2, TYPE: "insteon/properties/load", DEVICE_ADDRESS: "22.22.22"}
        )
        msg = await ws_client.receive_json()
        assert not msg["success"]
        assert msg["error"]["code"] == "load_failed"


async def test_reset_properties(hass, hass_ws_client, properties_data):
    """Test getting an Insteon device's properties."""
    ws_client, devices = await _setup(hass, hass_ws_client, properties_data)

    device = devices["33.33.33"]
    device.operating_flags["led_off"].new_value = True
    device.properties["on_mask"].new_value = 100
    assert device.operating_flags["led_off"].is_dirty
    assert device.properties["on_mask"].is_dirty
    with patch.object(insteon.api.properties, "devices", devices):
        await ws_client.send_json(
            {ID: 2, TYPE: "insteon/properties/reset", DEVICE_ADDRESS: "33.33.33"}
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert not device.operating_flags["led_off"].is_dirty
        assert not device.properties["on_mask"].is_dirty


async def test_bad_address(hass, hass_ws_client, properties_data):
    """Test for a bad Insteon address."""
    ws_client, _ = await _setup(hass, hass_ws_client, properties_data)

    ws_id = 0
    for call in ["get", "write", "load", "reset"]:
        ws_id += 1
        await ws_client.send_json(
            {
                ID: ws_id,
                TYPE: f"insteon/properties/{call}",
                DEVICE_ADDRESS: "99.99.99",
            }
        )
        msg = await ws_client.receive_json()
        assert not msg["success"]
        assert msg["error"]["message"] == INSTEON_DEVICE_NOT_FOUND

    ws_id += 1
    await ws_client.send_json(
        {
            ID: ws_id,
            TYPE: "insteon/properties/change",
            DEVICE_ADDRESS: "99.99.99",
            PROPERTY_NAME: "led_off",
            PROPERTY_VALUE: True,
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["message"] == INSTEON_DEVICE_NOT_FOUND
