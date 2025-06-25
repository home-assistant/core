"""Common methods for Sense."""

from __future__ import annotations

from collections.abc import Generator
import datetime
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from sense_energy import Scale

from homeassistant.components.sense.binary_sensor import SenseDevice
from homeassistant.components.sense.const import DOMAIN

from .const import (
    DEVICE_1_DAY_ENERGY,
    DEVICE_1_ID,
    DEVICE_1_NAME,
    DEVICE_1_POWER,
    DEVICE_2_DAY_ENERGY,
    DEVICE_2_ID,
    DEVICE_2_NAME,
    DEVICE_2_POWER,
    MOCK_CONFIG,
    MONITOR_ID,
)

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.sense.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Mock sense config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        unique_id="test-email",
    )


@pytest.fixture
def mock_sense() -> Generator[MagicMock]:
    """Mock an ASyncSenseable object with a split foundation."""
    with patch("homeassistant.components.sense.ASyncSenseable", autospec=True) as mock:
        gateway = mock.return_value
        gateway.sense_monitor_id = MONITOR_ID
        gateway.get_monitor_data.return_value = None
        gateway.update_realtime.return_value = None
        gateway.fetch_devices.return_value = None
        gateway.update_trend_data.return_value = None

        type(gateway).active_power = PropertyMock(return_value=100)
        type(gateway).active_solar_power = PropertyMock(return_value=500)
        type(gateway).active_voltage = PropertyMock(return_value=[120, 240])
        gateway.get_stat.return_value = 15
        gateway.trend_start.return_value = datetime.datetime.fromisoformat(
            "2024-01-01 01:01:00+00:00"
        )

        device_1 = SenseDevice(DEVICE_1_ID)
        device_1.name = DEVICE_1_NAME
        device_1.icon = "car"
        device_1.is_on = False
        device_1.power_w = DEVICE_1_POWER
        device_1.energy_kwh[Scale.DAY] = DEVICE_1_DAY_ENERGY

        device_2 = SenseDevice(DEVICE_2_ID)
        device_2.name = DEVICE_2_NAME
        device_2.icon = "stove"
        device_2.is_on = False
        device_2.power_w = DEVICE_2_POWER
        device_2.energy_kwh[Scale.DAY] = DEVICE_2_DAY_ENERGY
        type(gateway).devices = PropertyMock(return_value=[device_1, device_2])

        yield gateway
