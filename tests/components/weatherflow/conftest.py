"""Fixtures for Weatherflow integration tests."""

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pyweatherflowudp.client import EVENT_DEVICE_DISCOVERED
from pyweatherflowudp.device import WeatherFlowDevice

from homeassistant.components.weatherflow.const import DOMAIN

from tests.common import MockConfigEntry, load_json_object_fixture


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
    return MockConfigEntry(domain=DOMAIN, data={})


@pytest.fixture
def mock_has_devices() -> Generator[AsyncMock, None, None]:
    """Return a mock has_devices function."""
    with patch(
        "homeassistant.components.weatherflow.config_flow.WeatherFlowListener.on",
        return_value=True,
    ) as mock_has_devices:
        yield mock_has_devices


@pytest.fixture
def mock_stop() -> Generator[AsyncMock, None, None]:
    """Return a fixture to handle the stop of udp."""

    async def mock_stop_listening(self):
        self._udp_task.cancel()

    with patch(
        "homeassistant.components.weatherflow.config_flow.WeatherFlowListener.stop_listening",
        autospec=True,
        side_effect=mock_stop_listening,
    ) as mock_function:
        yield mock_function


@pytest.fixture
def mock_start() -> Generator[AsyncMock, None, None]:
    """Return fixture for starting upd."""

    device = WeatherFlowDevice(
        serial_number="HB-00000001",
        data=load_json_object_fixture("weatherflow/device.json"),
    )

    async def device_discovery_task(self):
        await asyncio.gather(
            await asyncio.sleep(0.1), self.emit(EVENT_DEVICE_DISCOVERED, "HB-00000001")
        )

    async def mock_start_listening(self):
        """Mock listening function."""
        self._devices["HB-00000001"] = device
        self._udp_task = asyncio.create_task(device_discovery_task(self))

    with patch(
        "homeassistant.components.weatherflow.config_flow.WeatherFlowListener.start_listening",
        autospec=True,
        side_effect=mock_start_listening,
    ) as mock_function:
        yield mock_function
