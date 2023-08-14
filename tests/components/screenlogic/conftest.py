"""Setup fixtures for ScreenLogic intigration tests."""
from collections.abc import Callable
from unittest.mock import AsyncMock, Mock, PropertyMock

import pytest
from screenlogicpy import ScreenLogicGateway
from screenlogicpy.const.data import ATTR, DEVICE, GROUP, VALUE
from screenlogicpy.device_const.system import EQUIPMENT_FLAG

from homeassistant.components.screenlogic import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT, CONF_SCAN_INTERVAL

from tests.common import MockConfigEntry

MOCK_ADAPTER_NAME = "Pentair DD-EE-FF"
MOCK_ADAPTER_MAC = "aa:bb:cc:dd:ee:ff"
MOCK_ADAPTER_IP = "127.0.0.1"
MOCK_ADAPTER_PORT = 80
MOCK_MIGRATION_TEST_DATA = {
    "adapter": {
        "firmware": {
            "name": "Protocol Adapter Firmware",
            "value": "POOL: 5.2 Build 736.0 Rel",
        }
    },
    "controller": {
        "controller_id": 100,
        "configuration": {
            "body_type": {
                "0": {"min_setpoint": 40, "max_setpoint": 104},
                "1": {"min_setpoint": 40, "max_setpoint": 104},
            },
            "is_celsius": {"name": "Is Celsius", "value": 0},
            "controller_type": 13,
            "hardware_type": 0,
        },
        "model": {"name": "Model", "value": "EasyTouch2 8"},
        "equipment": {
            "flags": 32796,
        },
        "sensor": {
            "active_alert": {
                "name": "Active Alert",
                "value": 0,
                "device_type": "alarm",
            },
        },
    },
    "circuit": {},
    "pump": {
        0: {
            "data": 70,
            "type": 3,
            "state": {"name": "Pool Low Pump", "value": 0},
            "watts_now": {
                "name": "Pool Low Pump Watts Now",
                "value": 0,
                "unit": "W",
                "device_type": "power",
                "state_type": "measurement",
            },
            "rpm_now": {
                "name": "Pool Low Pump RPM Now",
                "value": 0,
                "unit": "rpm",
                "state_type": "measurement",
            },
        },
        1: {"data": 0},
        2: {"data": 0},
        3: {"data": 0},
        4: {"data": 0},
        5: {"data": 0},
        6: {"data": 0},
        7: {"data": 0},
    },
    "body": {},
    "intellichem": {
        "unknown_at_offset_00": 42,
        "unknown_at_offset_04": 0,
        "sensor": {
            "ph_now": {
                "name": "pH Now",
                "value": 0.0,
                "unit": "pH",
                "state_type": "measurement",
            },
            "orp_now": {
                "name": "ORP Now",
                "value": 0,
                "unit": "mV",
                "state_type": "measurement",
            },
        },
    },
    "scg": {
        "scg_present": 1,
        "sensor": {
            "state": {"name": "Chlorinator", "value": 0},
            "salt_ppm": {
                "name": "Chlorinator Salt",
                "value": 0,
                "unit": "ppm",
                "state_type": "measurement",
            },
        },
        "configuration": {
            "pool_setpoint": {
                "name": "Pool Chlorinator Setpoint",
                "value": 51,
                "unit": "%",
                "min_setpoint": 0,
                "max_setpoint": 100,
                "step": 5,
                "body_type": 0,
            },
            "spa_setpoint": {
                "name": "Spa Chlorinator Setpoint",
                "value": 0,
                "unit": "%",
                "min_setpoint": 0,
                "max_setpoint": 100,
                "step": 5,
                "body_type": 1,
            },
            "super_chlor_timer": {
                "name": "Super Chlorination Timer",
                "value": 0,
                "unit": "hr",
                "min_setpoint": 1,
                "max_setpoint": 72,
                "step": 1,
            },
        },
        "flags": 0,
    },
}

MOCK_CLEANUP_TEST_DATA = {
    "adapter": {
        "firmware": {
            "name": "Protocol Adapter Firmware",
            "value": "POOL: 5.2 Build 736.0 Rel",
        }
    },
    "controller": {
        "controller_id": 100,
        "configuration": {
            "body_type": {
                "0": {"min_setpoint": 40, "max_setpoint": 104},
                "1": {"min_setpoint": 40, "max_setpoint": 104},
            },
            "is_celsius": {"name": "Is Celsius", "value": 0},
            "controller_type": 13,
            "hardware_type": 0,
        },
        "model": {"name": "Model", "value": "EasyTouch2 8"},
        "equipment": {
            "flags": 24,
        },
    },
    "circuit": {},
    "pump": {
        0: {"data": 0},
        1: {"data": 0},
        2: {"data": 0},
        3: {"data": 0},
        4: {"data": 0},
        5: {"data": 0},
        6: {"data": 0},
        7: {"data": 0},
    },
    "body": {},
    "intellichem": {},
    "scg": {},
}


def create_mock_gateway(mock_data):
    """Create a mock connected ScreenLogicGateway."""

    async def mock_async_connect(
        self,
        ip=None,
        port=None,
        gtype=None,
        gsubtype=None,
        name=None,
        connection_closed_callback: Callable = None,
    ) -> bool:
        """Connect to the ScreenLogic protocol adapter."""
        self._ip = ip
        self._port = port
        self._type = gtype
        self._subtype = gsubtype
        self._name = name
        self._custom_connection_closed_callback = connection_closed_callback
        self._mac = MOCK_ADAPTER_MAC
        self._data = mock_data

        return True

    def mock_get_data(*keypath, strict: bool = False):
        if not keypath:
            return mock_data

        next_key = mock_data

        def get_next(key):
            if current is None:
                return None
            if isinstance(current, dict):
                return current.get(key)
            if isinstance(current, list) and key in range(len(current)):
                return current[key]
            return None

        for key in keypath:
            current = next_key
            next_key = get_next(key)
            if next_key is None:
                if strict:
                    raise KeyError(f"'{key}' not found in '{keypath}'")
                break
        return next_key

    gateway = Mock(spec=ScreenLogicGateway)
    type(gateway).async_connect = AsyncMock(return_value=mock_async_connect)
    type(gateway).get_data = Mock(side_effect=mock_get_data)
    type(gateway).is_connected = PropertyMock(return_value=True)
    type(gateway).is_client = PropertyMock(return_value=False)
    type(gateway).equipment_flags = PropertyMock(
        return_value=EQUIPMENT_FLAG(
            mock_data[DEVICE.CONTROLLER][GROUP.EQUIPMENT][VALUE.FLAGS]
        )
    )
    type(gateway).name = PropertyMock(return_value=MOCK_ADAPTER_NAME)
    type(gateway).version = PropertyMock(
        return_value=mock_data[DEVICE.ADAPTER][VALUE.FIRMWARE][ATTR.VALUE]
    )
    type(gateway).controller_model = PropertyMock(
        return_value=mock_data[DEVICE.CONTROLLER][VALUE.MODEL][ATTR.VALUE]
    )
    return gateway


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(
        title=MOCK_ADAPTER_NAME,
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: MOCK_ADAPTER_IP,
            CONF_PORT: MOCK_ADAPTER_PORT,
        },
        options={
            CONF_SCAN_INTERVAL: 30,
        },
        unique_id=MOCK_ADAPTER_MAC,
    )


@pytest.fixture
def mock_migration_gateway():
    """Return a mocked connected ScreenLogicGateway with data for testing entity migration."""
    return create_mock_gateway(MOCK_MIGRATION_TEST_DATA)


@pytest.fixture
def mock_cleanup_gateway():
    """Return a mocked connected ScreenLogicGateway with data for testing excluded entity cleanup."""
    return create_mock_gateway(MOCK_CLEANUP_TEST_DATA)
