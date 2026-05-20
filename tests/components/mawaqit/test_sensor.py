"""Tests for the Mawaqit sensor platform."""

from unittest.mock import AsyncMock, MagicMock, patch

from freezegun import freeze_time

from homeassistant.components.mawaqit.coordinator import (
    MosqueCoordinator,
    PrayerTimeCoordinator,
)
from homeassistant.components.mawaqit.sensor import (
    NEXT_SALAT_SENSOR_DESCRIPTION,
    PRAYER_TIME_SENSOR_DESCRIPTIONS,
    MawaqitPrayerTimeSensor,
    MawaqitPrayerTimeSensorEntityDescription,
    MyMosqueSensor,
    NextPrayerSensor,
    SensorEntityDescription,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_MOSQUE_DATA = {
    "name": "Test Mosque",
    "uuid": "aaaaa-bbbbb-cccccc-0000",
    "announcements": [
        {"title": "Ramadan", "content": "Starts tomorrow"},
    ],
}


def _build_prayer_data() -> dict:
    """Build mock prayer data with calendar for April 10."""
    month_data = {}
    for day in range(1, 32):
        month_data[str(day)] = ["05:30", "06:45", "12:30", "15:45", "18:30", "20:00"]

    calendar = [{} for _ in range(12)]
    calendar[3] = month_data  # April

    iqama_month_data = {}
    for day in range(1, 32):
        iqama_month_data[str(day)] = ["+10", "+15", "+10", "+5", "+10"]

    iqama_calendar = [{} for _ in range(12)]
    iqama_calendar[3] = iqama_month_data

    return {
        "calendar": calendar,
        "iqamaCalendar": iqama_calendar,
        "timezone": "Europe/Paris",
        "shuruq": "06:45",
        "jumua": "13:00",
        "jumua2": "14:00",
    }


async def _setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mosque_data: dict | None = None,
    prayer_data: dict | None = None,
) -> None:
    """Set up the Mawaqit integration with mocked data."""
    if mosque_data is None:
        mosque_data = MOCK_MOSQUE_DATA
    if prayer_data is None:
        prayer_data = _build_prayer_data()

    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.fetch_mosque_by_id",
            new_callable=AsyncMock,
            return_value=mosque_data,
        ),
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.fetch_prayer_times",
            new_callable=AsyncMock,
            return_value=prayer_data,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


@freeze_time("2025-04-10 12:00:00+02:00")
async def test_sensor_setup_creates_entities(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that all sensor entities are created."""
    await _setup_integration(hass, mock_config_entry)

    # Check all entities exist by listing them
    states = hass.states.async_all("sensor")
    entity_ids = [s.entity_id for s in states]

    # We expect: 1 mosque + 6 prayer + 2 jumua + 5 iqama + 2 next_prayer = 16
    assert len(entity_ids) == 16


@freeze_time("2025-04-10 12:00:00+02:00")
async def test_mosque_sensor_native_value(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test mosque sensor returns the mosque name."""
    await _setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.mosque_information")
    assert state is not None
    assert state.state == "Test Mosque"


@freeze_time("2025-04-10 12:00:00+02:00")
async def test_mosque_sensor_extra_state_attributes(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test mosque sensor has announcement attributes."""
    await _setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.mosque_information")
    assert state is not None
    assert "announcements" in state.attributes
    assert state.attributes["announcements"] == ["Ramadan - Starts tomorrow"]


@freeze_time("2025-04-10 12:00:00+02:00")
async def test_mosque_sensor_no_announcements(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test mosque sensor with no announcements."""
    mosque_data = {"name": "Test Mosque", "uuid": "abc"}
    await _setup_integration(hass, mock_config_entry, mosque_data=mosque_data)

    state = hass.states.get("sensor.mosque_information")
    assert state is not None
    assert "announcements" not in state.attributes


@freeze_time("2025-04-10 12:00:00+02:00")
async def test_mosque_sensor_no_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test mosque sensor when coordinator data is None."""
    await _setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data.mosque_coordinator
    coordinator.data = None
    coordinator.async_set_updated_data(None)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.mosque_information")
    assert state is not None
    assert state.state == "unavailable"


@freeze_time("2025-04-10 12:00:00+02:00")
async def test_prayer_time_sensor_values(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test prayer time sensors return valid datetime values."""
    await _setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.fajr_prayer")
    assert state is not None
    assert state.state != "unavailable"
    assert state.state != "unknown"


@freeze_time("2025-04-10 12:00:00+02:00")
async def test_prayer_time_sensor_no_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test prayer time sensor when coordinator data is None."""
    await _setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data.prayer_time_coordinator
    coordinator.data = None
    coordinator.async_set_updated_data(None)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.fajr_prayer")
    assert state is not None
    assert state.state == "unavailable"


@freeze_time("2025-04-10 12:00:00+02:00")
async def test_prayer_time_sensor_get_value_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test prayer time sensor when get_value raises an exception."""
    await _setup_integration(hass, mock_config_entry)

    # Set prayer data to something that causes errors in utility functions
    coordinator = mock_config_entry.runtime_data.prayer_time_coordinator
    coordinator.async_set_updated_data({"invalid": "data"})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.fajr_prayer")
    assert state is not None
    assert state.state == "unknown"


@freeze_time("2025-04-10 12:00:00+02:00")
async def test_next_prayer_sensor_name(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test next prayer name sensor."""
    await _setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.next_salat_name")
    assert state is not None
    assert state.state != "unavailable"
    assert state.state != "unknown"
    # At 12:00 Paris time, next prayer should be Dhuhr (12:30)
    assert state.state == "dhuhr"


@freeze_time("2025-04-10 12:00:00+02:00")
async def test_next_prayer_sensor_time(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test next prayer time sensor."""
    await _setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.next_salat_time")
    assert state is not None
    assert state.state != "unavailable"
    assert state.state != "unknown"


@freeze_time("2025-04-10 12:00:00+02:00")
async def test_next_prayer_sensor_no_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test next prayer sensor when coordinator data is None."""
    await _setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data.prayer_time_coordinator
    coordinator.data = None
    coordinator.async_set_updated_data(None)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.next_salat_name")
    assert state is not None
    assert state.state == "unavailable"


@freeze_time("2025-04-10 12:00:00+02:00")
async def test_next_prayer_sensor_no_calendar(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test next prayer sensor when calendar is missing from data."""
    await _setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data.prayer_time_coordinator
    coordinator.async_set_updated_data({"timezone": "Europe/Paris"})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.next_salat_name")
    assert state is not None
    assert state.state == "unknown"


@freeze_time("2025-04-10 12:00:00+02:00")
async def test_shuruq_sensor(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test shuruq sensor returns valid time."""
    await _setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.shuruq")
    assert state is not None
    assert state.state != "unavailable"
    assert state.state != "unknown"


@freeze_time("2025-04-10 12:00:00+02:00")
async def test_jumua_sensor(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test jumua sensor returns valid time."""
    await _setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.jumua_prayer")
    assert state is not None
    assert state.state != "unavailable"


@freeze_time("2025-04-10 12:00:00+02:00")
async def test_iqama_sensor(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test iqama sensor returns valid time."""
    await _setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.fajr_iqama")
    assert state is not None
    assert state.state != "unavailable"
    assert state.state != "unknown"


# --- Direct unit tests for sensor classes to cover property branches ---


def test_mosque_sensor_native_value_no_data() -> None:
    """Test MyMosqueSensor.native_value returns None when no data."""
    coordinator = MagicMock(spec=MosqueCoordinator)
    coordinator.data = None
    sensor = MyMosqueSensor(coordinator, "My mosque")
    assert sensor.native_value is None


def test_mosque_sensor_extra_state_attributes_no_data() -> None:
    """Test MyMosqueSensor.extra_state_attributes returns None when no data."""
    coordinator = MagicMock(spec=MosqueCoordinator)
    coordinator.data = None
    sensor = MyMosqueSensor(coordinator, "My mosque")
    assert sensor.extra_state_attributes is None


def test_prayer_time_sensor_native_value_no_data() -> None:
    """Test MawaqitPrayerTimeSensor.native_value returns None when no data."""
    coordinator = MagicMock(spec=PrayerTimeCoordinator)
    coordinator.data = None
    desc = PRAYER_TIME_SENSOR_DESCRIPTIONS[0]
    sensor = MawaqitPrayerTimeSensor(coordinator, desc)
    assert sensor.native_value is None


def test_prayer_time_sensor_native_value_raises() -> None:
    """Test MawaqitPrayerTimeSensor.native_value returns None on exception."""
    coordinator = MagicMock(spec=PrayerTimeCoordinator)
    coordinator.data = {"some": "data"}
    desc = MawaqitPrayerTimeSensorEntityDescription(
        key="test",
        translation_key="test",
        device_class=SensorDeviceClass.TIMESTAMP,
        get_value=MagicMock(side_effect=KeyError("missing")),
    )
    sensor = MawaqitPrayerTimeSensor(coordinator, desc)
    assert sensor.native_value is None


def test_next_prayer_sensor_no_data_direct() -> None:
    """Test NextPrayerSensor._get_next_prayer_info returns None tuple when no data."""
    coordinator = MagicMock(spec=PrayerTimeCoordinator)
    coordinator.data = None
    desc = NEXT_SALAT_SENSOR_DESCRIPTION[0]
    sensor = NextPrayerSensor(coordinator, desc)
    assert sensor.native_value is None


def test_next_prayer_sensor_unknown_key() -> None:
    """Test NextPrayerSensor.native_value returns None for unknown key."""
    coordinator = MagicMock(spec=PrayerTimeCoordinator)
    # Provide valid data so _get_next_prayer_info returns actual values
    month_data = {}
    for day in range(1, 32):
        month_data[str(day)] = ["05:30", "06:45", "12:30", "15:45", "18:30", "20:00"]
    calendar = [{} for _ in range(12)]
    calendar[3] = month_data  # April

    coordinator.data = {
        "calendar": calendar,
        "timezone": "Europe/Paris",
    }
    desc = SensorEntityDescription(
        key="unknown_key",
        translation_key="unknown_key",
    )
    sensor = NextPrayerSensor(coordinator, desc)
    # next_prayer_index and time are not None, but key doesn't match any known key
    assert sensor.native_value is None
