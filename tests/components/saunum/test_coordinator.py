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
    hass: HomeAssistant, config_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """Test update fails when communication error occurs."""
    client = MagicMock()
    client.async_get_data = AsyncMock(
        side_effect=SaunumCommunicationError("connection failed")
    )
    coord = _make_coordinator(hass, config_entry, client)

    with pytest.raises(UpdateFailed):
        await coord._async_update_data()

    assert "Device became unavailable" in caplog.text


@pytest.mark.asyncio
async def test_update_connection_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """Test update fails when connection error occurs."""
    client = MagicMock()
    client.async_get_data = AsyncMock(
        side_effect=SaunumConnectionError("cannot connect")
    )
    coord = _make_coordinator(hass, config_entry, client)

    with pytest.raises(UpdateFailed):
        await coord._async_update_data()

    assert "Device became unavailable" in caplog.text


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
    hass: HomeAssistant, config_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """Test device communication restored log message."""
    client = MagicMock()

    # First call fails
    client.async_get_data = AsyncMock(
        side_effect=SaunumCommunicationError("connection error")
    )
    coord = _make_coordinator(hass, config_entry, client)

    with pytest.raises(UpdateFailed):
        await coord._async_update_data()

    assert "Device became unavailable" in caplog.text

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
    assert "Device communication restored" in caplog.text


@pytest.mark.asyncio
async def test_start_session_success(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test successful session start."""
    client = MagicMock()
    client.async_start_session = AsyncMock()
    client.async_get_data = AsyncMock(return_value=_make_mock_data())
    coord = _make_coordinator(hass, config_entry, client)

    result = await coord.async_start_session()

    assert result is True
    client.async_start_session.assert_awaited_once()
    client.async_get_data.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_session_failure(
    hass: HomeAssistant, config_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """Test session start failure."""
    client = MagicMock()
    client.async_start_session = AsyncMock(
        side_effect=SaunumCommunicationError("write failed")
    )
    coord = _make_coordinator(hass, config_entry, client)

    result = await coord.async_start_session()

    assert result is False
    assert "Error starting session" in caplog.text


@pytest.mark.asyncio
async def test_stop_session_success(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test successful session stop."""
    client = MagicMock()
    client.async_stop_session = AsyncMock()
    client.async_get_data = AsyncMock(return_value=_make_mock_data())
    coord = _make_coordinator(hass, config_entry, client)

    result = await coord.async_stop_session()

    assert result is True
    client.async_stop_session.assert_awaited_once()
    client.async_get_data.assert_awaited_once()


@pytest.mark.asyncio
async def test_stop_session_failure(
    hass: HomeAssistant, config_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """Test session stop failure."""
    client = MagicMock()
    client.async_stop_session = AsyncMock(
        side_effect=SaunumCommunicationError("write failed")
    )
    coord = _make_coordinator(hass, config_entry, client)

    result = await coord.async_stop_session()

    assert result is False
    assert "Error stopping session" in caplog.text


@pytest.mark.asyncio
async def test_set_target_temperature_success(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test successful temperature setting."""
    client = MagicMock()
    client.async_set_target_temperature = AsyncMock()
    client.async_get_data = AsyncMock(return_value=_make_mock_data())
    coord = _make_coordinator(hass, config_entry, client)

    result = await coord.async_set_target_temperature(85)

    assert result is True
    client.async_set_target_temperature.assert_awaited_once_with(85)
    client.async_get_data.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_target_temperature_failure(
    hass: HomeAssistant, config_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """Test temperature setting failure."""
    client = MagicMock()
    client.async_set_target_temperature = AsyncMock(
        side_effect=SaunumCommunicationError("write failed")
    )
    coord = _make_coordinator(hass, config_entry, client)

    result = await coord.async_set_target_temperature(85)

    assert result is False
    assert "Error setting target temperature" in caplog.text


@pytest.mark.asyncio
async def test_set_target_temperature_invalid_value(
    hass: HomeAssistant, config_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """Test temperature setting with invalid value."""
    client = MagicMock()
    client.async_set_target_temperature = AsyncMock(
        side_effect=ValueError("Temperature out of range")
    )
    coord = _make_coordinator(hass, config_entry, client)

    result = await coord.async_set_target_temperature(200)

    assert result is False
    assert "Error setting target temperature" in caplog.text
