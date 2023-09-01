"""Test the asyncua integration."""
import asyncio
import copy
from typing import Any
import unittest
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, patch

from asyncua import ua
import pytest

from homeassistant.components.asyncua import AsyncuaCoordinator, OpcuaHub, async_setup
from homeassistant.components.asyncua.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.setup import async_setup_component

_MOCK_KEY_NOEID_PAIR = {"key1": "ns=1;s=1", "key2": "ns=1;s=2"}
_MOCK_KEY_NODEID = list(_MOCK_KEY_NOEID_PAIR.keys())


@mock.patch("homeassistant.components.asyncua.OpcuaHub.get_values")
async def test_setup_duplicate_hub_name(
    mock_hub_get_values: dict[str, Any],
    hass: HomeAssistant,
) -> None:
    """Ensure error is raised if asyncua hub is configured more than once."""
    mock_hub_get_values.return_value = {"mock-node": 99}
    hubs = [
        {
            "name": "mock-hub",
            "url": "opc.tcp://mock-url:mock-port",
            "manufacturer": "mock-manufacturer",
            "model": "mock-model",
            "scan_interval": 30,
            "username": "mock-username",
            "password": "mock-password",
        },
        {
            "name": "mock-hub",
            "url": "opc.tcp://mock-url:mock-port",
            "manufacturer": "mock-manufacturer",
            "model": "mock-model",
            "scan_interval": 30,
            "username": "mock-username",
            "password": "mock-password",
        },
    ]
    with pytest.raises(ConfigEntryError):
        await async_setup(hass=hass, config={DOMAIN: hubs})
        await hass.async_block_till_done()


@mock.patch("homeassistant.components.asyncua.OpcuaHub.get_values")
async def test_setup_pass(
    mock_hub_get_values: dict[str, Any],
    hass: HomeAssistant,
) -> None:
    """Test the setup."""
    mock_hub_get_values.return_value = {"mock-node": 99}
    await async_setup_component(
        hass=hass,
        domain=DOMAIN,
        config={
            DOMAIN: [
                {
                    "name": "mock-hub",
                    "url": "opc.tcp://mock-url:mock-port",
                    "scan_interval": 30,
                }
            ]
        },
    )
    assert "mock-hub" in hass.data[DOMAIN]
    assert type(hass.data[DOMAIN]["mock-hub"]) == AsyncuaCoordinator
    assert mock_hub_get_values.call_count == 1


class TestOpcuaHub_Credential(unittest.TestCase):
    """Test for setting asyncua credentials."""

    def setUp(self) -> None:
        """Set up asyncua coordinator and hub."""
        self.mock_asyncua_coordinator = MagicMock()
        self.mock_hub = OpcuaHub(
            hub_name="mock-hub",
            hub_manufacturer="mock-manufacturer",
            hub_model="mock-a1b1",
            hub_url="localhost:48480",
            username="admin",
            password="admin",
        )

    def tearDown(self) -> None:
        """Remove asyncua coordinator and hub."""
        del self.mock_asyncua_coordinator
        del self.mock_hub

    def test_set_credential_pass(self) -> None:
        """Test credentials are configured."""
        self.assertEqual("admin", self.mock_hub.client._username)
        self.assertEqual("admin", self.mock_hub.client._password)


class TestOpcuaHub_GetValues(unittest.TestCase):
    """Test for reading values from OPCUA node."""

    def setUp(self) -> None:
        """Set up asyncua coordinator and hub."""
        self.mock_asyncua_coordinator = MagicMock()
        self.mock_hub = OpcuaHub(
            hub_name="mock-hub",
            hub_manufacturer="mock-manufacturer",
            hub_model="mock-a1b1",
            hub_url="localhost:48480",
        )
        self.mock_hub.client = self.mock_asyncua_coordinator

    def tearDown(self) -> None:
        """Remove asyncua coordinator and hub."""
        del self.mock_asyncua_coordinator
        del self.mock_hub

    def test_get_values_runtime_error(self):
        """Ensure error is raised on run time error using wrapper function."""
        self.mock_asyncua_coordinator.get_node = MagicMock()
        self.mock_asyncua_coordinator.get_node.side_effect = RuntimeError(
            "unittest runtime error"
        )
        result = asyncio.get_event_loop().run_until_complete(
            future=self.mock_hub.get_values(node_key_pair=_MOCK_KEY_NOEID_PAIR),
        )
        self.assertIsNone(result)

    def test_get_values_timeout(self):
        """Ensure error is raised on timeout error using wrapper function."""
        self.mock_asyncua_coordinator.get_node = MagicMock()
        self.mock_asyncua_coordinator.get_node.side_effect = TimeoutError(
            "unittest timeout error"
        )
        with self.assertRaises(ConfigEntryNotReady):
            result = asyncio.get_event_loop().run_until_complete(
                future=self.mock_hub.get_values(node_key_pair=_MOCK_KEY_NOEID_PAIR),
            )
            self.assertIsNone(result)

    def test_get_values_connection_refuse(self):
        """Ensure error is raised on connection refused error using wrapper function."""
        self.mock_asyncua_coordinator.get_node = MagicMock()
        self.mock_asyncua_coordinator.get_node.side_effect = ConnectionRefusedError(
            "unittest connection refuse error"
        )
        with self.assertRaises(ConfigEntryAuthFailed):
            result = asyncio.get_event_loop().run_until_complete(
                future=self.mock_hub.get_values(node_key_pair=_MOCK_KEY_NOEID_PAIR),
            )
            self.assertIsNone(result)

    def test_get_values_invalid_argument(self):
        """Ensure no value is returned if an invalid dict argument is provided."""
        result = asyncio.get_event_loop().run_until_complete(
            future=self.mock_hub.get_values(node_key_pair={}),
        )
        self.assertDictEqual({}, result)

    def test_get_values_pass(self):
        """Test the event."""
        self.mock_asyncua_coordinator.get_node.return_value = None
        self.mock_asyncua_coordinator.read_values = AsyncMock()
        self.mock_asyncua_coordinator.read_values.return_value = [
            f"value_{key}" for key, val in _MOCK_KEY_NOEID_PAIR.items()
        ]
        result = asyncio.get_event_loop().run_until_complete(
            future=self.mock_hub.get_values(node_key_pair=_MOCK_KEY_NOEID_PAIR),
        )
        expected = dict(
            zip(
                _MOCK_KEY_NODEID, self.mock_asyncua_coordinator.read_values.return_value
            )
        )
        self.assertEqual(expected, result)


class TestOpcuaHub_SetValue(unittest.TestCase):
    """Test for setting new value to OPCUA node."""

    def setUp(self) -> None:
        """Set up asyncua coordinator and hub."""
        self.mock_asyncua_coordinator = MagicMock()
        self.mock_hub = OpcuaHub(
            hub_name="mock-hub",
            hub_manufacturer="mock-manufacturer",
            hub_model="mock-a1b1",
            hub_url="localhost:48480",
        )
        self.mock_hub.client = self.mock_asyncua_coordinator

    def tearDown(self) -> None:
        """Remove asyncua coordinator and hub."""
        del self.mock_asyncua_coordinator
        del self.mock_hub

    def test_set_value_runtime_error(self):
        """Ensure error is raised on run time error using wrapper function."""
        self.mock_asyncua_coordinator.get_node = MagicMock()
        self.mock_asyncua_coordinator.get_node.side_effect = RuntimeError(
            "unittest runtime error"
        )
        result = asyncio.get_event_loop().run_until_complete(
            future=self.mock_hub.set_value(nodeid="ns=1;s=1", value=1),
        )
        self.assertIsNone(result)

    def test_set_value_timeout(self):
        """Ensure error is raised on timeout error using wrapper function."""
        self.mock_asyncua_coordinator.get_node = MagicMock()
        self.mock_asyncua_coordinator.get_node.side_effect = TimeoutError(
            "unittest timeout error"
        )
        with self.assertRaises(ConfigEntryNotReady):
            result = asyncio.get_event_loop().run_until_complete(
                future=self.mock_hub.set_value(nodeid="ns=1;s=1", value=1),
            )
            self.assertIsNone(result)

    def test_set_value_connection_refuse(self):
        """Ensure error is raised on connection refused error using wrapper function."""
        self.mock_asyncua_coordinator.get_node = MagicMock()
        self.mock_asyncua_coordinator.get_node.side_effect = ConnectionRefusedError(
            "unittest connection refuse error"
        )
        with self.assertRaises(ConfigEntryAuthFailed):
            result = asyncio.get_event_loop().run_until_complete(
                future=self.mock_hub.set_value(nodeid="ns=1;s=1", value=1),
            )
            self.assertIsNone(result)

    @patch("asyncua.common.ua_utils.string_to_val")
    def test_set_value_pass(self, mock_string_to_val):
        """Test the event."""
        mock_string_to_val.return_value = None
        mock_node = AsyncMock()
        mock_node.read_data_type_as_variant_type.return_value = AsyncMock(
            return_value=ua.VariantType.Float
        )
        mock_node.write_value.return_value = AsyncMock()
        self.mock_asyncua_coordinator.get_node = MagicMock(return_value=mock_node)
        self.mock_asyncua_coordinator.write_value.return_value = None
        result = asyncio.get_event_loop().run_until_complete(
            future=self.mock_hub.set_value(nodeid="ns=1;s=1", value=1),
        )
        mock_node.read_data_type_as_variant_type.assert_called_once()
        mock_node.write_value.assert_called_once()
        self.assertTrue(result)


class TestAsyncuaCoordinator_AddSensors(unittest.TestCase):
    """Test adding sensors during setup process."""

    def setUp(self) -> None:
        """Set up asyncua coordinator, hub and sensors."""
        self.mock_hub = MagicMock()
        self.mock_coordinator = AsyncuaCoordinator(
            hass=MagicMock(),
            name="mock-plc-opcua-hub",
            hub=self.mock_hub,
        )
        self.mock_sensors = [
            {
                "name": "mock_sensor_01",
                "unique_id": "mock_sensor_01",
                "device_class": "temperature",
                "hub": "hub_01",
                "nodeid": "ns=1;s=mock_sensor_01",
            },
            {
                "name": "mock_sensor_02",
                "unique_id": "mock_sensor_02",
                "device_class": "temperature",
                "hub": "hub_01",
                "nodeid": "ns=1;s=mock_sensor_02",
            },
        ]

    def tearDown(self) -> None:
        """Remove asyncua coordinator, hub and sensors."""
        del self.mock_hub
        del self.mock_coordinator
        del self.mock_sensors

    def test_add_sensors_pass(self):
        """Test the event."""
        self.mock_coordinator.add_sensors(sensors=copy.deepcopy(self.mock_sensors))
        expected = {}
        for _idx, val in enumerate(self.mock_sensors):
            expected[val["name"]] = val["nodeid"]
        self.assertListEqual(self.mock_sensors, self.mock_coordinator.sensors)
        self.assertDictEqual(expected, self.mock_coordinator.node_key_pair)


class TestAsyncuaCoordinator_AsyncUpdateData(unittest.TestCase):
    """Test sensor value up from coordinator data."""

    def setUp(self) -> None:
        """Set up asyncua coordinator, hub and sensors."""
        self.mock_hub = AsyncMock()
        self.mock_coordinator = AsyncuaCoordinator(
            hass=MagicMock(),
            name="mock-plc-opcua-hub",
            hub=self.mock_hub,
        )
        self.mock_sensors = [
            {
                "name": "mock_sensor_01",
                "unique_id": "mock_sensor_01",
                "device_class": "temperature",
                "hub": "hub_01",
                "nodeid": "ns=1;s=mock_sensor_01",
            },
            {
                "name": "mock_sensor_02",
                "unique_id": "mock_sensor_02",
                "device_class": "temperature",
                "hub": "hub_01",
                "nodeid": "ns=1;s=mock_sensor_02",
            },
        ]
        self.mock_coordinator.add_sensors(sensors=copy.deepcopy(self.mock_sensors))

    def tearDown(self) -> None:
        """Remove asyncua coordinator, hub and sensors."""
        del self.mock_hub
        del self.mock_coordinator
        del self.mock_sensors

    def test_asyncua_update_data_errors(self):
        """Ensure no data is returned if coordinator data update error."""
        self.mock_hub.get_values.return_value = None
        expected = {}
        result = asyncio.get_event_loop().run_until_complete(
            future=self.mock_coordinator._async_update_data(),
        )
        self.assertEqual(expected, result)

    def test_asyncua_update_data_pass(self):
        """Test the event."""
        expected = {
            "mock_sensor_01": 11,
            "mock_sensor_02": 22,
        }
        self.mock_hub.get_values.return_value = expected
        result = asyncio.get_event_loop().run_until_complete(
            future=self.mock_coordinator._async_update_data(),
        )
        self.assertEqual(expected, result)
