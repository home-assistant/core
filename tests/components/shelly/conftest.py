"""Test configuration for Shelly."""
from unittest.mock import AsyncMock, Mock, patch

from aioshelly.block_device import BlockDevice
from aioshelly.rpc_device import RpcDevice
import pytest

from homeassistant.components.shelly.const import (
    EVENT_SHELLY_CLICK,
    REST_SENSORS_UPDATE_INTERVAL,
)

from . import MOCK_MAC

from tests.common import async_capture_events, async_mock_service, mock_device_registry

MOCK_SETTINGS = {
    "name": "Test name",
    "mode": "relay",
    "device": {
        "mac": MOCK_MAC,
        "hostname": "test-host",
        "type": "SHSW-25",
        "num_outputs": 2,
    },
    "coiot": {"update_period": 15},
    "fw": "20201124-092159/v1.9.0@57ac4ad8",
    "relays": [{"btn_type": "momentary"}, {"btn_type": "toggle"}],
    "rollers": [{"positioning": True}],
}


def mock_light_set_state(
    turn="on",
    mode="color",
    red=45,
    green=55,
    blue=65,
    white=70,
    gain=19,
    temp=4050,
    brightness=50,
    effect=0,
    transition=0,
):
    """Mock light block set_state."""
    return {
        "ison": turn == "on",
        "mode": mode,
        "red": red,
        "green": green,
        "blue": blue,
        "white": white,
        "gain": gain,
        "temp": temp,
        "brightness": brightness,
        "effect": effect,
        "transition": transition,
    }


MOCK_BLOCKS = [
    Mock(
        sensor_ids={"inputEvent": "S", "inputEventCnt": 2},
        channel="0",
        type="relay",
        set_state=AsyncMock(side_effect=lambda turn: {"ison": turn == "on"}),
    ),
    Mock(
        sensor_ids={"roller": "stop", "rollerPos": 0},
        channel="1",
        type="roller",
        set_state=AsyncMock(
            side_effect=lambda go, roller_pos=0: {
                "current_pos": roller_pos,
                "state": go,
            }
        ),
    ),
    Mock(
        sensor_ids={},
        channel="0",
        output=mock_light_set_state()["ison"],
        colorTemp=mock_light_set_state()["temp"],
        **mock_light_set_state(),
        type="light",
        set_state=AsyncMock(side_effect=mock_light_set_state),
    ),
]

MOCK_CONFIG = {
    "input:0": {"id": 0, "type": "button"},
    "switch:0": {"name": "test switch_0"},
    "cover:0": {"name": "test cover_0"},
    "sys": {
        "ui_data": {},
        "device": {"name": "Test name"},
    },
}

MOCK_SHELLY_COAP = {
    "mac": MOCK_MAC,
    "auth": False,
    "fw": "20201124-092854/v1.9.0@57ac4ad8",
    "num_outputs": 2,
}

MOCK_SHELLY_RPC = {
    "name": "Test Gen2",
    "id": "shellyplus2pm-123456789abc",
    "mac": MOCK_MAC,
    "model": "SNSW-002P16EU",
    "gen": 2,
    "fw_id": "20220830-130540/0.11.0-gfa1bc37",
    "ver": "0.11.0",
    "app": "Plus2PM",
    "auth_en": False,
    "auth_domain": None,
    "profile": "cover",
}

MOCK_STATUS_COAP = {
    "update": {
        "status": "pending",
        "has_update": True,
        "beta_version": "some_beta_version",
        "new_version": "some_new_version",
        "old_version": "some_old_version",
    },
    "uptime": 5 * REST_SENSORS_UPDATE_INTERVAL,
}


MOCK_STATUS_RPC = {
    "switch:0": {"output": True},
    "cover:0": {"state": "stopped", "pos_control": True, "current_pos": 50},
    "sys": {
        "available_updates": {
            "beta": {"version": "some_beta_version"},
            "stable": {"version": "some_beta_version"},
        }
    },
}


@pytest.fixture(autouse=True)
def mock_coap():
    """Mock out coap."""
    with patch(
        "homeassistant.components.shelly.utils.COAP",
        return_value=Mock(
            initialize=AsyncMock(),
            close=Mock(),
        ),
    ):
        yield


@pytest.fixture(autouse=True)
def mock_ws_server():
    """Mock out ws_server."""
    with patch("homeassistant.components.shelly.utils.get_ws_context"):
        yield


@pytest.fixture
def device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.fixture
def events(hass):
    """Yield caught shelly_click events."""
    return async_capture_events(hass, EVENT_SHELLY_CLICK)


@pytest.fixture
async def mock_block_device():
    """Mock block (Gen1, CoAP) device."""
    with patch("aioshelly.block_device.BlockDevice.create") as block_device_mock:

        def update():
            block_device_mock.return_value.subscribe_updates.call_args[0][0]({})

        device = Mock(
            spec=BlockDevice,
            blocks=MOCK_BLOCKS,
            settings=MOCK_SETTINGS,
            shelly=MOCK_SHELLY_COAP,
            status=MOCK_STATUS_COAP,
            firmware_version="some fw string",
            initialized=True,
        )
        block_device_mock.return_value = device
        block_device_mock.return_value.mock_update = Mock(side_effect=update)

        yield block_device_mock.return_value


@pytest.fixture
async def mock_rpc_device():
    """Mock rpc (Gen2, Websocket) device."""
    with patch("aioshelly.rpc_device.RpcDevice.create") as rpc_device_mock:

        def update():
            rpc_device_mock.return_value.subscribe_updates.call_args[0][0]({})

        device = Mock(
            spec=RpcDevice,
            config=MOCK_CONFIG,
            event={},
            shelly=MOCK_SHELLY_RPC,
            status=MOCK_STATUS_RPC,
            firmware_version="some fw string",
            initialized=True,
        )

        rpc_device_mock.return_value = device
        rpc_device_mock.return_value.mock_update = Mock(side_effect=update)

        yield rpc_device_mock.return_value
