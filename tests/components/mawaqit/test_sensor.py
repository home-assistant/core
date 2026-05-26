"""Tests for the Mawaqit sensor platform."""

from unittest.mock import AsyncMock, MagicMock, patch

from freezegun import freeze_time
import pytest

from homeassistant.components.mawaqit.coordinator import (
    MosqueCoordinator,
    PrayerTimeCoordinator,
)
from homeassistant.components.mawaqit.sensor import (
    PRAYER_TIME_SENSOR_DESCRIPTIONS,
    MawaqitPrayerTimeSensor,
    MawaqitPrayerTimeSensorEntityDescription,
    MyMosqueSensor,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_MOSQUE_DATA = {"name": "Test Mosque", "uuid": "aaaaa-bbbbb-cccccc-0000"}


def _build_prayer_data(
    *,
    iqama_enabled: bool = True,
    with_iqama_calendar: bool = True,
    jumua: str | None = "13:00",
    jumua2: str | None = "14:00",
    jumua3: str | None = None,
) -> dict:
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
        "iqamaCalendar": iqama_calendar if with_iqama_calendar else [],
        "iqamaEnabled": iqama_enabled,
        "timezone": "Europe/Paris",
        "shuruq": "06:45",
        "jumua": jumua,
        "jumua2": jumua2,
        "jumua3": jumua3,
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
@pytest.mark.parametrize(
    ("prayer_data_kwargs", "expected_count"),
    [
        ({}, 16),  # 1 + 6 + 2 jumua + 5 iqama + 2 = 16
        ({"iqama_enabled": False}, 11),  # no iqama
        ({"with_iqama_calendar": False}, 11),  # no iqama
        ({"jumua2": None}, 15),  # 1 jumua only
        ({"jumua3": "15:00"}, 17),  # 3 jumua
        ({"jumua2": None, "iqama_enabled": False}, 10),  # 1 jumua, no iqama
    ],
)
async def test_sensor_setup_creates_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    prayer_data_kwargs: dict,
    expected_count: int,
) -> None:
    """Test that the correct number of entities is created based on mosque capabilities."""
    await _setup_integration(
        hass, mock_config_entry, prayer_data=_build_prayer_data(**prayer_data_kwargs)
    )
    assert len(hass.states.async_all("sensor")) == expected_count


@freeze_time("2025-04-10 12:00:00+02:00")
@pytest.mark.parametrize(
    ("prayer_data_kwargs", "entity_id", "should_exist"),
    [
        ({}, "sensor.fajr_iqama", True),
        ({"iqama_enabled": False}, "sensor.fajr_iqama", False),
        ({"with_iqama_calendar": False}, "sensor.fajr_iqama", False),
        ({}, "sensor.jumua_prayer", True),
        ({"jumua": None}, "sensor.jumua_prayer", False),
        ({}, "sensor.second_jumua_prayer", True),
        ({"jumua2": None}, "sensor.second_jumua_prayer", False),
        ({"jumua3": "15:00"}, "sensor.third_jumua_prayer", True),
        ({"jumua3": None}, "sensor.third_jumua_prayer", False),
    ],
)
async def test_conditional_sensor_creation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    prayer_data_kwargs: dict,
    entity_id: str,
    should_exist: bool,
) -> None:
    """Test that jumua and iqama sensors are created only when the API reports them."""
    await _setup_integration(
        hass, mock_config_entry, prayer_data=_build_prayer_data(**prayer_data_kwargs)
    )
    assert (hass.states.get(entity_id) is not None) == should_exist


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
@pytest.mark.parametrize(
    ("coordinator_attr", "entity_id"),
    [
        ("mosque_coordinator", "sensor.mosque_information"),
        ("prayer_time_coordinator", "sensor.fajr_prayer"),
        ("prayer_time_coordinator", "sensor.next_salat_name"),
    ],
)
async def test_sensor_unavailable_when_no_coordinator_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    coordinator_attr: str,
    entity_id: str,
) -> None:
    """Test sensors become unavailable when coordinator data is None."""
    await _setup_integration(hass, mock_config_entry)
    coordinator = getattr(mock_config_entry.runtime_data, coordinator_attr)
    coordinator.async_set_updated_data(None)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
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
async def test_next_prayer_sensors(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test next salat sensors: at 12:00 Paris the next prayer is Dhuhr at 12:30."""
    await _setup_integration(hass, mock_config_entry)

    name_state = hass.states.get("sensor.next_salat_name")
    assert name_state is not None
    assert name_state.state == "dhuhr"

    time_state = hass.states.get("sensor.next_salat_time")
    assert time_state is not None
    assert time_state.state not in ("unavailable", "unknown")


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
@pytest.mark.parametrize(
    "entity_id",
    ["sensor.fajr_prayer", "sensor.shuruq", "sensor.jumua_prayer"],
)
async def test_prayer_sensors_return_valid_state(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, entity_id: str
) -> None:
    """Test prayer, shuruq and jumua sensors return a valid datetime state."""
    await _setup_integration(hass, mock_config_entry)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state not in ("unavailable", "unknown")


# --- Direct unit tests for sensor classes to cover property branches ---


@pytest.mark.parametrize(
    ("sensor_cls", "coordinator_spec", "extra_args"),
    [
        (MyMosqueSensor, MosqueCoordinator, []),
        (
            MawaqitPrayerTimeSensor,
            PrayerTimeCoordinator,
            [PRAYER_TIME_SENSOR_DESCRIPTIONS[0]],
        ),
    ],
)
def test_sensor_native_value_none_when_no_data(
    sensor_cls, coordinator_spec, extra_args
) -> None:
    """Test native_value returns None when coordinator data is None."""
    coordinator = MagicMock(spec=coordinator_spec)
    coordinator.data = None
    sensor = sensor_cls(coordinator, *extra_args)
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
