"""Test configuration for Shelly."""
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.shelly import (
    BlockDeviceWrapper,
    RpcDeviceWrapper,
    RpcPollingWrapper,
    ShellyDeviceRestWrapper,
)
from homeassistant.components.shelly.const import (
    BLOCK,
    DATA_CONFIG_ENTRY,
    DOMAIN,
    EVENT_SHELLY_CLICK,
    REST,
    REST_SENSORS_UPDATE_INTERVAL,
    RPC,
    RPC_POLL,
)
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    async_capture_events,
    async_mock_service,
    mock_device_registry,
)

MOCK_SETTINGS = {
    "name": "Test name",
    "mode": "relay",
    "device": {
        "mac": "test-mac",
        "hostname": "test-host",
        "type": "SHSW-25",
        "num_outputs": 2,
    },
    "coiot": {"update_period": 15},
    "fw": "20201124-092159/v1.9.0@57ac4ad8",
    "relays": [{"btn_type": "momentary"}, {"btn_type": "toggle"}],
    "rollers": [{"positioning": True}],
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
    "mac": "test-mac",
    "auth": False,
    "fw": "20201124-092854/v1.9.0@57ac4ad8",
    "num_outputs": 2,
}

MOCK_SHELLY_RPC = {
    "name": "Test Gen2",
    "id": "shellyplus2pm-123456789abc",
    "mac": "123456789ABC",
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
    with patch("homeassistant.components.shelly.utils.get_coap_context"):
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
async def coap_wrapper(hass):
    """Setups a coap wrapper with mocked device."""
    await async_setup_component(hass, "shelly", {})

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"sleep_period": 0, "model": "SHSW-25", "host": "1.2.3.4"},
        unique_id="12345678",
    )
    config_entry.add_to_hass(hass)

    device = Mock(
        blocks=MOCK_BLOCKS,
        settings=MOCK_SETTINGS,
        shelly=MOCK_SHELLY_COAP,
        status=MOCK_STATUS_COAP,
        firmware_version="some fw string",
        update=AsyncMock(),
        update_status=AsyncMock(),
        trigger_ota_update=AsyncMock(),
        trigger_reboot=AsyncMock(),
        initialized=True,
    )

    hass.data[DOMAIN] = {DATA_CONFIG_ENTRY: {}}
    hass.data[DOMAIN][DATA_CONFIG_ENTRY][config_entry.entry_id] = {}
    hass.data[DOMAIN][DATA_CONFIG_ENTRY][config_entry.entry_id][
        REST
    ] = ShellyDeviceRestWrapper(hass, device, config_entry)

    wrapper = hass.data[DOMAIN][DATA_CONFIG_ENTRY][config_entry.entry_id][
        BLOCK
    ] = BlockDeviceWrapper(hass, config_entry, device)

    wrapper.async_setup()

    return wrapper


@pytest.fixture
async def rpc_wrapper(hass):
    """Setups a rpc wrapper with mocked device."""
    await async_setup_component(hass, "shelly", {})

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"sleep_period": 0, "model": "SNSW-001P16EU", "gen": 2, "host": "1.2.3.4"},
        unique_id="12345678",
    )
    config_entry.add_to_hass(hass)

    device = Mock(
        call_rpc=AsyncMock(),
        config=MOCK_CONFIG,
        event={},
        shelly=MOCK_SHELLY_RPC,
        status=MOCK_STATUS_RPC,
        firmware_version="some fw string",
        update=AsyncMock(),
        trigger_ota_update=AsyncMock(),
        trigger_reboot=AsyncMock(),
        initialized=True,
        shutdown=AsyncMock(),
    )

    hass.data[DOMAIN] = {DATA_CONFIG_ENTRY: {}}
    hass.data[DOMAIN][DATA_CONFIG_ENTRY][config_entry.entry_id] = {}
    hass.data[DOMAIN][DATA_CONFIG_ENTRY][config_entry.entry_id][
        RPC_POLL
    ] = RpcPollingWrapper(hass, config_entry, device)

    wrapper = hass.data[DOMAIN][DATA_CONFIG_ENTRY][config_entry.entry_id][
        RPC
    ] = RpcDeviceWrapper(hass, config_entry, device)
    wrapper.async_setup()

    return wrapper
