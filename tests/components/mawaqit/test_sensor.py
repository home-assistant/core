"""Tests for the Mawaqit sensor platform."""

from datetime import datetime
from unittest.mock import MagicMock

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
    NextPrayerSensor,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription
from homeassistant.core import HomeAssistant

from .conftest import build_prayer_data

from tests.common import MockConfigEntry

# ---------------------------------------------------------------------------
# Sensor setup tests
# ---------------------------------------------------------------------------


@freeze_time("2025-04-10 12:00:00+02:00")
@pytest.mark.parametrize(
    ("prayer_data_kwargs", "expected_count"),
    [
        ({}, 16),  # 1 mosque + 6 prayers + 2 jumua + 5 iqama + 2 next = 16
        ({"iqama_enabled": False}, 11),  # no iqama sensors
        ({"with_iqama_calendar": False}, 11),  # no iqama sensors
        ({"jumua2": None}, 15),  # only 1 Jumua
        ({"jumua3": "15:00"}, 17),  # 3 Jumua prayers
        ({"jumua2": None, "iqama_enabled": False}, 10),  # 1 Jumua, no iqama
    ],
)
async def test_sensor_setup_creates_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    setup_mawaqit_integration,
    prayer_data_kwargs: dict,
    expected_count: int,
) -> None:
    """Test that the correct number of entities is created based on mosque capabilities."""
    await setup_mawaqit_integration(
        prayer_data=build_prayer_data(fill_all_months=False, **prayer_data_kwargs)
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
    setup_mawaqit_integration,
    prayer_data_kwargs: dict,
    entity_id: str,
    should_exist: bool,
) -> None:
    """Test that Jumua and iqama sensors are created only when the API reports them."""
    await setup_mawaqit_integration(
        prayer_data=build_prayer_data(fill_all_months=False, **prayer_data_kwargs)
    )
    assert (hass.states.get(entity_id) is not None) == should_exist


@freeze_time("2025-04-10 12:00:00+02:00")
async def test_mosque_sensor_native_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    setup_mawaqit_integration,
) -> None:
    """Test mosque sensor returns the mosque name."""
    await setup_mawaqit_integration(
        prayer_data=build_prayer_data(fill_all_months=False)
    )

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
    setup_mawaqit_integration,
    coordinator_attr: str,
    entity_id: str,
) -> None:
    """Test sensors become unavailable when coordinator data is None."""
    await setup_mawaqit_integration(
        prayer_data=build_prayer_data(fill_all_months=False)
    )
    coordinator = getattr(mock_config_entry.runtime_data, coordinator_attr)
    coordinator.async_set_updated_data(None)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unavailable"


@freeze_time("2025-04-10 12:00:00+02:00")
async def test_prayer_time_sensor_get_value_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    setup_mawaqit_integration,
) -> None:
    """Test prayer time sensor when get_value raises an exception."""
    await setup_mawaqit_integration(
        prayer_data=build_prayer_data(fill_all_months=False)
    )

    coordinator = mock_config_entry.runtime_data.prayer_time_coordinator
    coordinator.async_set_updated_data({"invalid": "data"})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.fajr_prayer")
    assert state is not None
    assert state.state == "unknown"


@freeze_time("2025-04-10 12:00:00+02:00")
async def test_next_prayer_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    setup_mawaqit_integration,
) -> None:
    """Test next salat sensors: at 12:00 Paris the next prayer is Dhuhr at 12:30."""
    await setup_mawaqit_integration(
        prayer_data=build_prayer_data(fill_all_months=False)
    )

    name_state = hass.states.get("sensor.next_salat_name")
    assert name_state is not None
    assert name_state.state == "dhuhr"

    time_state = hass.states.get("sensor.next_salat_time")
    assert time_state is not None
    assert time_state.state not in ("unavailable", "unknown")


@freeze_time("2025-04-10 12:00:00+02:00")
async def test_next_prayer_sensor_no_calendar(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    setup_mawaqit_integration,
) -> None:
    """Test next prayer sensor when calendar is missing from data."""
    await setup_mawaqit_integration(
        prayer_data=build_prayer_data(fill_all_months=False)
    )

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
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    setup_mawaqit_integration,
    entity_id: str,
) -> None:
    """Test prayer, shuruq and jumua sensors return a valid datetime state."""
    await setup_mawaqit_integration(
        prayer_data=build_prayer_data(fill_all_months=False)
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state not in ("unavailable", "unknown")


# ---------------------------------------------------------------------------
# Direct unit tests for sensor class property branches
# ---------------------------------------------------------------------------


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


def test_next_prayer_sensor_native_value_unhandled_key() -> None:
    """Test NextPrayerSensor returns None for a description key it does not handle."""
    coordinator = MagicMock(spec=PrayerTimeCoordinator)
    sensor = NextPrayerSensor(coordinator, SensorEntityDescription(key="unhandled"))
    sensor._next_prayer_index = 2
    sensor._next_prayer_time = datetime(2025, 4, 10, 12, 30)
    assert sensor.native_value is None
