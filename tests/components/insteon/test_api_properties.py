"""Test the Insteon properties APIs."""
import json
from unittest.mock import AsyncMock, patch

from pyinsteon.config import MOMENTARY_DELAY, RELAY_MODE, TOGGLE_BUTTON
from pyinsteon.config.extended_property import ExtendedProperty
from pyinsteon.constants import RelayMode, ToggleMode
import pytest

from homeassistant.components import insteon
from homeassistant.components.insteon.api import async_load_api
from homeassistant.components.insteon.api.device import INSTEON_DEVICE_NOT_FOUND
from homeassistant.components.insteon.api.properties import (
    DEVICE_ADDRESS,
    ID,
    PROPERTY_NAME,
    PROPERTY_VALUE,
    RADIO_BUTTON_GROUPS,
    RAMP_RATE_IN_SEC,
    SHOW_ADVANCED,
    TYPE,
)
from homeassistant.core import HomeAssistant

from .mock_devices import MockDevices

from tests.common import load_fixture
from tests.typing import WebSocketGenerator


@pytest.fixture(name="kpl_properties_data", scope="session")
def kpl_properties_data_fixture():
    """Load the controller state fixture data."""
    return json.loads(load_fixture("insteon/kpl_properties.json"))


@pytest.fixture(name="iolinc_properties_data", scope="session")
def iolinc_properties_data_fixture():
    """Load the controller state fixture data."""
    return json.loads(load_fixture("insteon/iolinc_properties.json"))


async def _setup(hass, hass_ws_client, address, properties_data):
    """Set up tests."""
    ws_client = await hass_ws_client(hass)
    devices = MockDevices()
    await devices.async_load()
    devices.fill_properties(address, properties_data)
    async_load_api(hass)
    return ws_client, devices


async def test_get_properties(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    kpl_properties_data,
    iolinc_properties_data,
) -> None:
    """Test getting an Insteon device's properties."""
    ws_client, devices = await _setup(
        hass, hass_ws_client, "33.33.33", kpl_properties_data
    )
    devices.fill_properties("44.44.44", iolinc_properties_data)

    with patch.object(insteon.api.properties, "devices", devices):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "insteon/properties/get",
                DEVICE_ADDRESS: "33.33.33",
                SHOW_ADVANCED: False,
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert len(msg["result"]["properties"]) == 18

        await ws_client.send_json(
            {
                ID: 3,
                TYPE: "insteon/properties/get",
                DEVICE_ADDRESS: "44.44.44",
                SHOW_ADVANCED: False,
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert len(msg["result"]["properties"]) == 6

        await ws_client.send_json(
            {
                ID: 4,
                TYPE: "insteon/properties/get",
                DEVICE_ADDRESS: "33.33.33",
                SHOW_ADVANCED: True,
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert len(msg["result"]["properties"]) == 69

        await ws_client.send_json(
            {
                ID: 5,
                TYPE: "insteon/properties/get",
                DEVICE_ADDRESS: "44.44.44",
                SHOW_ADVANCED: True,
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert len(msg["result"]["properties"]) == 14


async def test_get_read_only_properties(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, iolinc_properties_data
) -> None:
    """Test getting an Insteon device's properties."""
    mock_read_only = ExtendedProperty(
        "44.44.44", "mock_read_only", bool, is_read_only=True
    )
    mock_read_only.load(False)

    ws_client, devices = await _setup(
        hass, hass_ws_client, "44.44.44", iolinc_properties_data
    )
    device = devices["44.44.44"]
    device.configuration["mock_read_only"] = mock_read_only
    with patch.object(insteon.api.properties, "devices", devices):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "insteon/properties/get",
                DEVICE_ADDRESS: "44.44.44",
                SHOW_ADVANCED: False,
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert len(msg["result"]["properties"]) == 6
        await ws_client.send_json(
            {
                ID: 3,
                TYPE: "insteon/properties/get",
                DEVICE_ADDRESS: "44.44.44",
                SHOW_ADVANCED: True,
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert len(msg["result"]["properties"]) == 15


async def test_get_unknown_properties(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, iolinc_properties_data
) -> None:
    """Test getting an Insteon device's properties."""

    class UnknownType:
        """Mock unknown data type."""

    mock_unknown = ExtendedProperty("44.44.44", "mock_unknown", UnknownType)

    ws_client, devices = await _setup(
        hass, hass_ws_client, "44.44.44", iolinc_properties_data
    )
    device = devices["44.44.44"]
    device.configuration["mock_unknown"] = mock_unknown
    with patch.object(insteon.api.properties, "devices", devices):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "insteon/properties/get",
                DEVICE_ADDRESS: "44.44.44",
                SHOW_ADVANCED: False,
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert len(msg["result"]["properties"]) == 6
        await ws_client.send_json(
            {
                ID: 3,
                TYPE: "insteon/properties/get",
                DEVICE_ADDRESS: "44.44.44",
                SHOW_ADVANCED: True,
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert len(msg["result"]["properties"]) == 14


async def test_change_bool_property(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, kpl_properties_data
) -> None:
    """Test changing a bool type properties."""
    ws_client, devices = await _setup(
        hass, hass_ws_client, "33.33.33", kpl_properties_data
    )

    with patch.object(insteon.api.properties, "devices", devices):
        await ws_client.send_json(
            {
                ID: 3,
                TYPE: "insteon/properties/change",
                DEVICE_ADDRESS: "33.33.33",
                PROPERTY_NAME: "led_off",
                PROPERTY_VALUE: True,
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert devices["33.33.33"].operating_flags["led_off"].is_dirty


async def test_change_int_property(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, kpl_properties_data
) -> None:
    """Test changing a int type properties."""
    ws_client, devices = await _setup(
        hass, hass_ws_client, "33.33.33", kpl_properties_data
    )

    with patch.object(insteon.api.properties, "devices", devices):
        await ws_client.send_json(
            {
                ID: 4,
                TYPE: "insteon/properties/change",
                DEVICE_ADDRESS: "33.33.33",
                PROPERTY_NAME: "led_dimming",
                PROPERTY_VALUE: 100,
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert devices["33.33.33"].properties["led_dimming"].new_value == 100
        assert devices["33.33.33"].properties["led_dimming"].is_dirty


async def test_change_ramp_rate_property(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, kpl_properties_data
) -> None:
    """Test changing an Insteon device's ramp rate properties."""
    ws_client, devices = await _setup(
        hass, hass_ws_client, "33.33.33", kpl_properties_data
    )

    with patch.object(insteon.api.properties, "devices", devices):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "insteon/properties/change",
                DEVICE_ADDRESS: "33.33.33",
                PROPERTY_NAME: RAMP_RATE_IN_SEC,
                PROPERTY_VALUE: 4.5,
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert devices["33.33.33"].properties["ramp_rate"].new_value == 0x1A
        assert devices["33.33.33"].properties["ramp_rate"].is_dirty


async def test_change_radio_button_group(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, kpl_properties_data
) -> None:
    """Test changing an Insteon device's properties."""
    ws_client, devices = await _setup(
        hass, hass_ws_client, "33.33.33", kpl_properties_data
    )
    rb_groups = devices["33.33.33"].configuration[RADIO_BUTTON_GROUPS]

    # Make sure the baseline is correct
    assert rb_groups.value[0] == [4, 5]
    assert rb_groups.value[1] == [7, 8]

    # Add button 1 to the group
    new_groups_1 = [[1, 4, 5], [7, 8]]
    with patch.object(insteon.api.properties, "devices", devices):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "insteon/properties/change",
                DEVICE_ADDRESS: "33.33.33",
                PROPERTY_NAME: RADIO_BUTTON_GROUPS,
                PROPERTY_VALUE: new_groups_1,
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert rb_groups.new_value[0] == [1, 4, 5]
        assert rb_groups.new_value[1] == [7, 8]

        new_groups_2 = [[1, 4], [7, 8]]
        await ws_client.send_json(
            {
                ID: 3,
                TYPE: "insteon/properties/change",
                DEVICE_ADDRESS: "33.33.33",
                PROPERTY_NAME: RADIO_BUTTON_GROUPS,
                PROPERTY_VALUE: new_groups_2,
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert rb_groups.new_value[0] == [1, 4]
        assert rb_groups.new_value[1] == [7, 8]


async def test_change_toggle_property(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, kpl_properties_data
) -> None:
    """Update a button's toggle mode."""
    ws_client, devices = await _setup(
        hass, hass_ws_client, "33.33.33", kpl_properties_data
    )
    device = devices["33.33.33"]
    prop_name = f"{TOGGLE_BUTTON}_c"
    toggle_prop = device.configuration[prop_name]
    assert toggle_prop.value == ToggleMode.TOGGLE
    with patch.object(insteon.api.properties, "devices", devices):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "insteon/properties/change",
                DEVICE_ADDRESS: "33.33.33",
                PROPERTY_NAME: prop_name,
                PROPERTY_VALUE: str(ToggleMode.ON_ONLY).lower(),
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert toggle_prop.new_value == ToggleMode.ON_ONLY


async def test_change_relay_mode(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, iolinc_properties_data
) -> None:
    """Update a device's relay mode."""
    ws_client, devices = await _setup(
        hass, hass_ws_client, "44.44.44", iolinc_properties_data
    )
    device = devices["44.44.44"]
    relay_prop = device.configuration[RELAY_MODE]
    assert relay_prop.value == RelayMode.MOMENTARY_A
    with patch.object(insteon.api.properties, "devices", devices):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "insteon/properties/change",
                DEVICE_ADDRESS: "44.44.44",
                PROPERTY_NAME: RELAY_MODE,
                PROPERTY_VALUE: str(RelayMode.LATCHING).lower(),
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert relay_prop.new_value == RelayMode.LATCHING


async def test_change_float_property(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, iolinc_properties_data
) -> None:
    """Update a float type property."""
    ws_client, devices = await _setup(
        hass, hass_ws_client, "44.44.44", iolinc_properties_data
    )
    device = devices["44.44.44"]
    delay_prop = device.configuration[MOMENTARY_DELAY]
    delay_prop.load(0)
    with patch.object(insteon.api.properties, "devices", devices):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "insteon/properties/change",
                DEVICE_ADDRESS: "44.44.44",
                PROPERTY_NAME: MOMENTARY_DELAY,
                PROPERTY_VALUE: 1.8,
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]

        assert delay_prop.new_value == 1.8


async def test_write_properties(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, kpl_properties_data
) -> None:
    """Test getting an Insteon device's properties."""
    ws_client, devices = await _setup(
        hass, hass_ws_client, "33.33.33", kpl_properties_data
    )

    with patch.object(insteon.api.properties, "devices", devices):
        await ws_client.send_json(
            {ID: 2, TYPE: "insteon/properties/write", DEVICE_ADDRESS: "33.33.33"}
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert devices["33.33.33"].async_write_op_flags.call_count == 1
        assert devices["33.33.33"].async_write_ext_properties.call_count == 1


async def test_write_properties_failure(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, kpl_properties_data
) -> None:
    """Test getting an Insteon device's properties."""
    ws_client, devices = await _setup(
        hass, hass_ws_client, "33.33.33", kpl_properties_data
    )

    with patch.object(insteon.api.properties, "devices", devices):
        await ws_client.send_json(
            {ID: 2, TYPE: "insteon/properties/write", DEVICE_ADDRESS: "22.22.22"}
        )
        msg = await ws_client.receive_json()
        assert not msg["success"]
        assert msg["error"]["code"] == "write_failed"


async def test_load_properties(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, kpl_properties_data
) -> None:
    """Test getting an Insteon device's properties."""
    ws_client, devices = await _setup(
        hass, hass_ws_client, "33.33.33", kpl_properties_data
    )

    device = devices["33.33.33"]
    device.async_read_config = AsyncMock(return_value=1)
    with patch.object(insteon.api.properties, "devices", devices):
        await ws_client.send_json(
            {ID: 2, TYPE: "insteon/properties/load", DEVICE_ADDRESS: "33.33.33"}
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert devices["33.33.33"].async_read_config.call_count == 1


async def test_load_properties_failure(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, kpl_properties_data
) -> None:
    """Test getting an Insteon device's properties."""
    ws_client, devices = await _setup(
        hass, hass_ws_client, "33.33.33", kpl_properties_data
    )

    device = devices["33.33.33"]
    device.async_read_config = AsyncMock(return_value=0)
    with patch.object(insteon.api.properties, "devices", devices):
        await ws_client.send_json(
            {ID: 2, TYPE: "insteon/properties/load", DEVICE_ADDRESS: "33.33.33"}
        )
        msg = await ws_client.receive_json()
        assert not msg["success"]
        assert msg["error"]["code"] == "load_failed"


async def test_reset_properties(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, kpl_properties_data
) -> None:
    """Test getting an Insteon device's properties."""
    ws_client, devices = await _setup(
        hass, hass_ws_client, "33.33.33", kpl_properties_data
    )

    device = devices["33.33.33"]
    device.configuration["led_off"].new_value = True
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


async def test_bad_address(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, kpl_properties_data
) -> None:
    """Test for a bad Insteon address."""
    ws_client, devices = await _setup(
        hass, hass_ws_client, "33.33.33", kpl_properties_data
    )

    ws_id = 0
    for call in ["get", "write", "load", "reset"]:
        ws_id += 1
        params = {
            ID: ws_id,
            TYPE: f"insteon/properties/{call}",
            DEVICE_ADDRESS: "99.99.99",
        }
        if call == "get":
            params[SHOW_ADVANCED] = False
        await ws_client.send_json(params)
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
