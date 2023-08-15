"""Fixtures for IntelliFire integration tests."""
import asyncio
from collections.abc import Generator
import json
from unittest.mock import AsyncMock, patch

import pytest
from pyweatherflowudp.client import EVENT_DEVICE_DISCOVERED
from pyweatherflowudp.const import DEFAULT_HOST
from pyweatherflowudp.device import WeatherFlowDevice
from pyweatherflowudp.errors import AddressInUseError, ListenerError

from homeassistant.components.weatherflow.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.weatherflow.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "1.2.3.4"})


@pytest.fixture
def mock_config_entry2() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(domain=DOMAIN, data={CONF_HOST: DEFAULT_HOST})


@pytest.fixture
def mock_has_devices() -> Generator[AsyncMock, None, None]:
    """Return a mock has_devices function."""
    with patch(
        "homeassistant.components.weatherflow.config_flow._async_has_devices",
        return_value=True,
    ) as mock_has_devices:
        yield mock_has_devices


@pytest.fixture
def mock_has_no_devices() -> Generator[AsyncMock, None, None]:
    """Return a mock has_devices function returning False."""
    with patch(
        "homeassistant.components.weatherflow.config_flow._async_has_devices",
        return_value=False,
    ) as mock_has_devices:
        yield mock_has_devices


@pytest.fixture
def mock_has_devices_error_listener() -> Generator[AsyncMock, None, None]:
    """Return a mock has_devices returning an error."""
    with patch(
        "homeassistant.components.weatherflow.config_flow._async_has_devices",
        side_effect=ListenerError,
    ) as mock_has_devices:
        yield mock_has_devices


@pytest.fixture
def mock_has_devices_error_address_in_use() -> Generator[AsyncMock, None, None]:
    """Return a mock has_devices returning an error."""
    with patch(
        "homeassistant.components.weatherflow.config_flow._async_has_devices",
        side_effect=AddressInUseError,
    ) as mock_has_devices:
        yield mock_has_devices


@pytest.fixture
def mock_stop() -> Generator[AsyncMock, None, None]:
    """Return a fixture to handle the stop of udp."""

    async def mock_stop_listening(self):
        self._udp_task.cancel()

    with patch(
        "pyweatherflowudp.client.WeatherFlowListener.stop_listening",
        autospec=True,
        side_effect=mock_stop_listening,
    ) as mock_function:
        yield mock_function


@pytest.fixture
def mock_start() -> Generator[AsyncMock, None, None]:
    """Return fixture for starting upd."""
    DEVICE_JSON = """
{
  "serial_number": "ST-00000001",
  "type": "device_status",
  "hub_sn": "HB-00000001",
  "timestamp": 1510855923,
  "uptime": 2189,
  "voltage": 3.50,
  "firmware_revision": 17,
  "rssi": -17,
  "hub_rssi": -87,
  "sensor_status": 0,
  "debug": 0
}"""
    device = WeatherFlowDevice(
        serial_number="HB-00000001", data=json.loads(DEVICE_JSON)
    )

    async def device_discovery_task(self):
        await asyncio.gather(
            await asyncio.sleep(2), self.emit(EVENT_DEVICE_DISCOVERED, "HB-00000001")
        )

    async def mock_start_listening(self):
        """Mock listening function."""
        self._devices["HB-00000001"] = device
        self._udp_task = asyncio.create_task(device_discovery_task(self))
        self._udp_task.add_done_callback(lambda _: print("Done Callback"))  # noqa: T201

    with patch(
        "pyweatherflowudp.client.WeatherFlowListener.start_listening",
        autospec=True,
        side_effect=mock_start_listening,
    ) as mock_function:
        yield mock_function


@pytest.fixture
def mock_start_timeout() -> Generator[AsyncMock, None, None]:
    """Return fixture for starting upd."""

    async def device_discovery_task(self):
        await asyncio.sleep(2)

    async def mock_start_listening(self):
        """Mock listening function."""
        self._udp_task = asyncio.create_task(device_discovery_task(self))

    with patch(
        "pyweatherflowudp.client.WeatherFlowListener.start_listening",
        autospec=True,
        side_effect=mock_start_listening,
    ) as mock_function:
        yield mock_function
