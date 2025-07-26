"""Fixtures for Envertech EVT800 tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.envertech_evt800.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import MOCK_DEVICE, MOCK_USER_INPUT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""

    return MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_DEVICE["name"],
        unique_id=str(MOCK_DEVICE["serial"]),
        data=MOCK_USER_INPUT,
        minor_version=1,
        entry_id="evt800_entry_123",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock the setup entry."""
    with patch(
        "homeassistant.components.envertech_evt800.pyenvertechevt800.EnvertechEVT800",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_evt800_client() -> Generator[MagicMock]:
    """Mock the EVT800 client."""
    with patch(
        "homeassistant.components.envertech_evt800.pyenvertechevt800.EnvertechEVT800",
        autospec=True,
    ) as client:
        client.return_value.device_info.return_value = MOCK_DEVICE
        client.online.return_value = True

        client.data.return_value = {
            "id_1": 39828832,
            "id_2": 39828833,
            "sw_version": "7A.7A",
            "input_voltage_1": 32.34375,
            "input_voltage_2": 24.595703125,
            "power_1": 182.09375,
            "power_2": 5.921875,
            "ac_voltage_1": 241.140625,
            "ac_voltage_2": 241.140625,
            "ac_frequency_1": 49.9921875,
            "ac_frequency_2": 49.9921875,
            "temperature_1": 53.09375,
            "temperature_2": 45.3984375,
            "total_energy_1": 5.8431396484375,
            "total_energy_2": 0.446533203125,
            "current_1": 0.7551351001101536,
            "current_2": 0.024557765826475734,
        }

        yield client
