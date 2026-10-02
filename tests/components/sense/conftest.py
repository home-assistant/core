"""Common methods for Sense."""

from collections.abc import Generator
from dataclasses import dataclass, field
import datetime
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from sense_energy import Scale

from homeassistant.components.recorder import Recorder
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
    HOURLY_ENERGY,
    MOCK_CONFIG,
    MONITOR_ID,
    PERIOD_TO_DATE,
)

from tests.common import MockConfigEntry
from tests.conftest import RecorderInstanceContextManager


@dataclass
class MockTrends:
    """The hourly trend data the mocked gateway serves."""

    # The hour the gateway last successfully fetched, as trend_start() reports it.
    start: datetime.datetime | None = None
    # Hours the monitor has no data for. Fetching one is a no-op, which leaves the
    # previously fetched hour in place, exactly as the library behaves.
    missing: set[datetime.datetime] = field(default_factory=set)
    energy: dict[str, float] = field(default_factory=lambda: dict(HOURLY_ENERGY))


@pytest.fixture
async def mock_recorder_before_hass(
    async_test_recorder: RecorderInstanceContextManager,
) -> None:
    """Set up the recorder, which sense depends on."""


@pytest.fixture
def mock_setup_entry(recorder_mock: Recorder) -> Generator[AsyncMock]:
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
def mock_trends() -> MockTrends:
    """Return the hourly trend data the mocked gateway serves."""
    return MockTrends()


@pytest.fixture
def mock_sense(
    recorder_mock: Recorder, mock_trends: MockTrends
) -> Generator[MagicMock]:
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

        async def get_trend_data(scale: Scale, dt: datetime.datetime) -> None:
            if scale is Scale.HOUR and dt not in mock_trends.missing:
                mock_trends.start = dt

        def trend_start(scale: Scale) -> datetime.datetime | None:
            if scale is Scale.HOUR:
                return mock_trends.start
            return datetime.datetime.fromisoformat("2024-01-01 01:01:00+00:00")

        def get_stat(scale: Scale, variant: str) -> float:
            if scale is Scale.HOUR:
                return mock_trends.energy[variant]
            return PERIOD_TO_DATE

        gateway.get_trend_data.side_effect = get_trend_data
        gateway.trend_start.side_effect = trend_start
        gateway.get_stat.side_effect = get_stat

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
