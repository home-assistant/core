"""The test for the moon sensor platform."""

from unittest.mock import patch

import pytest

from homeassistant.components.moon.helpers import (
    STATE_FIRST_QUARTER,
    STATE_FULL_MOON,
    STATE_LAST_QUARTER,
    STATE_NEW_MOON,
    STATE_WANING_CRESCENT,
    STATE_WANING_GIBBOUS,
    STATE_WAXING_CRESCENT,
    STATE_WAXING_GIBBOUS,
    moon,
)
from homeassistant.components.sensor import ATTR_OPTIONS, SensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_FRIENDLY_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("moon_value", "native_value"),
    [
        (0, STATE_NEW_MOON),
        (5, STATE_WAXING_CRESCENT),
        (7, STATE_FIRST_QUARTER),
        (12, STATE_WAXING_GIBBOUS),
        (14.3, STATE_FULL_MOON),
        (20.1, STATE_WANING_GIBBOUS),
        (20.8, STATE_LAST_QUARTER),
        (23, STATE_WANING_CRESCENT),
    ],
)
async def test_moon_day(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    moon_value: float,
    native_value: str,
) -> None:
    """Test the Moon sensor."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.moon.helpers.moon.phase", return_value=moon_value
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.moon_phase")
    assert state
    assert state.state == native_value
    assert state.attributes[ATTR_FRIENDLY_NAME] == "Moon Phase"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENUM
    assert state.attributes[ATTR_OPTIONS] == [
        STATE_NEW_MOON,
        STATE_WAXING_CRESCENT,
        STATE_FIRST_QUARTER,
        STATE_WAXING_GIBBOUS,
        STATE_FULL_MOON,
        STATE_WANING_GIBBOUS,
        STATE_LAST_QUARTER,
        STATE_WANING_CRESCENT,
    ]

    entry = entity_registry.async_get("sensor.moon_phase")
    assert entry
    assert entry.unique_id == mock_config_entry.entry_id
    assert entry.translation_key == "phase"

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Moon"
    assert device_entry.entry_type is dr.DeviceEntryType.SERVICE


@pytest.mark.parametrize(
    ("target_str", "expected_phase"),
    [
        pytest.param(
            "2026-08-27",
            13.411222222222223,
            id="date-midnight",
        ),
        pytest.param(
            "2026-08-27 22:56:00+00:00",
            14.26677777777778,
            id="datetime-utc",
        ),
        pytest.param(
            "2026-08-27 22:56:00",
            14.26677777777778,
            id="datetime-naive",
        ),
    ],
)
def test_moon_phase_calculation(target_str: str, expected_phase: float) -> None:
    """Test moon phase calculation across date and datetime inputs."""
    target = dt_util.parse_date(target_str) or dt_util.parse_datetime(target_str)
    assert target is not None
    assert moon.phase(target) == pytest.approx(expected_phase)


def test_moon_phase_default_now() -> None:
    """Test moon phase defaults to current time."""
    now = dt_util.parse_datetime("2026-08-27 22:56:00+00:00")
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        assert moon.phase() == pytest.approx(14.26677777777778)


async def test_moon_sensor_unmocked(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Moon sensor without mocking moon.phase."""
    now = dt_util.parse_datetime("2026-08-27 22:56:00+00:00")
    with patch("homeassistant.util.dt.now", return_value=now):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.moon_phase")
    assert state
    assert state.state == STATE_FULL_MOON
