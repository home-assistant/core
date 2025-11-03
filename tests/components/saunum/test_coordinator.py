"""Tests for Saunum coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from pysaunum import SaunumCommunicationError, SaunumConnectionError, SaunumData
import pytest

from homeassistant.components.saunum.const import DOMAIN
from homeassistant.components.saunum.coordinator import LeilSaunaCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Provide a config entry instance for coordinator tests."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "127.0.0.1", "port": 502},
        unique_id="127.0.0.1:502",
    )
    entry.add_to_hass(hass)
    return entry


def _make_coordinator(
    hass: HomeAssistant, config_entry: MockConfigEntry, client: MagicMock
) -> LeilSaunaCoordinator:
    """Create a coordinator with a mock client."""
    return LeilSaunaCoordinator(hass, client, config_entry)


def _make_mock_data(**kwargs) -> SaunumData:
    """Create mock SaunumData with default values."""
    defaults = {
        "session_active": False,
        "sauna_type": 0,
        "sauna_duration": 120,
        "fan_duration": 10,
        "target_temperature": 80,
        "fan_speed": 2,
        "light_on": False,
        "current_temperature": 75.0,
        "on_time": 3600,
        "heater_elements_active": 0,
        "door_open": False,
        "alarm_door_open": False,
        "alarm_door_sensor": False,
        "alarm_thermal_cutoff": False,
        "alarm_internal_temp": False,
        "alarm_temp_sensor_short": False,
        "alarm_temp_sensor_open": False,
    }
    defaults.update(kwargs)
    return SaunumData(**defaults)


@pytest.mark.asyncio
async def test_update_communication_error(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test update fails when communication error occurs."""
    client = MagicMock()
    client.async_get_data = AsyncMock(
        side_effect=SaunumCommunicationError("connection failed")
    )
    coord = _make_coordinator(hass, config_entry, client)

    with pytest.raises(UpdateFailed):
        await coord._async_update_data()


@pytest.mark.asyncio
async def test_update_connection_error(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test update fails when connection error occurs."""
    client = MagicMock()
    client.async_get_data = AsyncMock(
        side_effect=SaunumConnectionError("cannot connect")
    )
    coord = _make_coordinator(hass, config_entry, client)

    with pytest.raises(UpdateFailed):
        await coord._async_update_data()


@pytest.mark.asyncio
async def test_update_success(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test successful data update."""
    client = MagicMock()
    mock_data = SaunumData(
        session_active=True,
        sauna_type=0,
        sauna_duration=120,
        fan_duration=10,
        target_temperature=80,
        fan_speed=2,
        light_on=True,
        current_temperature=75.0,
        on_time=3600,
        heater_elements_active=2,
        door_open=False,
        alarm_door_open=False,
        alarm_door_sensor=False,
        alarm_thermal_cutoff=False,
        alarm_internal_temp=False,
        alarm_temp_sensor_short=False,
        alarm_temp_sensor_open=False,
    )
    client.async_get_data = AsyncMock(return_value=mock_data)
    coord = _make_coordinator(hass, config_entry, client)

    data = await coord._async_update_data()

    assert data == mock_data
    assert data.session_active is True
    assert data.target_temperature == 80
    assert data.current_temperature == 75.0


@pytest.mark.asyncio
async def test_communication_restored(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test device communication can be restored after failure."""
    client = MagicMock()

    # First call fails
    client.async_get_data = AsyncMock(
        side_effect=SaunumCommunicationError("connection error")
    )
    coord = _make_coordinator(hass, config_entry, client)

    with pytest.raises(UpdateFailed):
        await coord._async_update_data()

    # Second call succeeds
    mock_data = SaunumData(
        session_active=False,
        sauna_type=0,
        sauna_duration=120,
        fan_duration=10,
        target_temperature=80,
        fan_speed=2,
        light_on=False,
        current_temperature=75.0,
        on_time=3600,
        heater_elements_active=0,
        door_open=False,
        alarm_door_open=False,
        alarm_door_sensor=False,
        alarm_thermal_cutoff=False,
        alarm_internal_temp=False,
        alarm_temp_sensor_short=False,
        alarm_temp_sensor_open=False,
    )
    client.async_get_data = AsyncMock(return_value=mock_data)

    data = await coord._async_update_data()
    assert data is not None
