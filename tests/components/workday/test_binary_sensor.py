"""Tests the Home Assistant workday binary sensor."""
from typing import Any
from unittest.mock import MagicMock, patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.workday import update_listener
from homeassistant.components.workday.binary_sensor import WorkdayBinarySensor
from homeassistant.components.workday.const import DOMAIN
from homeassistant.const import CONF_NAME, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, State

from .fixtures import (
    ASSUMED_DATE,
    SENSOR_DATA,
    USER_INPUT,
    USER_INPUT_ADD_HOLIDAY,
    USER_INPUT_ADD_HOLIDAY_NO_WORKDAYS,
    USER_INPUT_ADD_HOLIDAY_NOT_EXCLUDED,
    USER_INPUT_ADD_HOLIDAY_ONLY_INCLUDED,
    USER_INPUT_EXCLUDE_TODAY,
)

from tests.common import MockConfigEntry


async def _async_build_sensor(
    sensor_data: dict[str, Any], options: dict[str, Any]
) -> WorkdayBinarySensor:
    """Build and update a Workday sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=sensor_data,
        options=options,
        unique_id=sensor_data[CONF_NAME],
    )
    sensor = WorkdayBinarySensor(entry)
    await sensor.async_update()

    return sensor


@patch(
    "homeassistant.components.workday.binary_sensor.get_date",
    return_value=ASSUMED_DATE,
)
@patch("homeassistant.components.workday.util.get_date", return_value=ASSUMED_DATE)
async def test_binary_sensor(
    mock_get_date: MagicMock, mock_sensor_get_date: MagicMock
) -> None:
    """Test the basic binary sensor."""
    sensor = await _async_build_sensor(SENSOR_DATA, USER_INPUT)

    # On the assumed date, today is not a holiday and it is a work day
    assert sensor.state == STATE_ON


@patch(
    "homeassistant.components.workday.binary_sensor.get_date",
    return_value=ASSUMED_DATE,
)
@patch("homeassistant.components.workday.util.get_date", return_value=ASSUMED_DATE)
async def test_binary_sensor_on_holiday(
    mock_get_date: MagicMock, mock_sensor_get_date: MagicMock
) -> None:
    """Test the basic binary sensor."""
    sensor = await _async_build_sensor(SENSOR_DATA, USER_INPUT_ADD_HOLIDAY)

    # On the assumed date, today has been added as a holiday and holidays are excluded
    assert sensor.state == STATE_OFF


@patch(
    "homeassistant.components.workday.binary_sensor.get_date",
    return_value=ASSUMED_DATE,
)
@patch("homeassistant.components.workday.util.get_date", return_value=ASSUMED_DATE)
async def test_binary_sensor_not_excluded_holiday(
    mock_get_date: MagicMock, mock_sensor_get_date: MagicMock
) -> None:
    """Test the basic binary sensor."""
    sensor = await _async_build_sensor(SENSOR_DATA, USER_INPUT_ADD_HOLIDAY_NOT_EXCLUDED)

    # On the assumed date, today has been added as a holiday but holidays are not
    # excluded
    assert sensor.state == STATE_ON


@patch(
    "homeassistant.components.workday.binary_sensor.get_date",
    return_value=ASSUMED_DATE,
)
@patch("homeassistant.components.workday.util.get_date", return_value=ASSUMED_DATE)
async def test_binary_sensor_only_including_holiday(
    mock_get_date: MagicMock, mock_sensor_get_date: MagicMock
) -> None:
    """Test the basic binary sensor."""
    sensor = await _async_build_sensor(
        SENSOR_DATA, USER_INPUT_ADD_HOLIDAY_ONLY_INCLUDED
    )

    # On the assumed date, today has been added as a holiday and holidays are included
    assert sensor.state == STATE_ON


@patch(
    "homeassistant.components.workday.binary_sensor.get_date",
    return_value=ASSUMED_DATE,
)
@patch("homeassistant.components.workday.util.get_date", return_value=ASSUMED_DATE)
async def test_binary_sensor_holiday_nothing_included(
    mock_get_date: MagicMock, mock_sensor_get_date: MagicMock
) -> None:
    """Test the basic binary sensor."""
    sensor = await _async_build_sensor(SENSOR_DATA, USER_INPUT_ADD_HOLIDAY_NO_WORKDAYS)

    # On the assumed date, today has been added as a holiday but no days are work days
    assert sensor.state == STATE_OFF


@patch(
    "homeassistant.components.workday.binary_sensor.get_date",
    return_value=ASSUMED_DATE,
)
@patch("homeassistant.components.workday.util.get_date", return_value=ASSUMED_DATE)
async def test_binary_sensor_exclude_today(
    mock_get_date: MagicMock, mock_sensor_get_date: MagicMock
) -> None:
    """Test the basic binary sensor."""
    sensor = await _async_build_sensor(SENSOR_DATA, USER_INPUT_EXCLUDE_TODAY)

    # On the assumed date, today is not a holiday but today is excluded
    assert sensor.state == STATE_OFF


@patch(
    "homeassistant.components.workday.binary_sensor.get_date",
    return_value=ASSUMED_DATE,
)
@patch("homeassistant.components.workday.util.get_date", return_value=ASSUMED_DATE)
@patch(
    "homeassistant.components.workday.binary_sensor.day_to_string",
    return_value=None,
)
async def test_binary_sensor_with_unknown_day(
    mock_get_date: MagicMock,
    mock_sensor_get_date: MagicMock,
    mock_day_to_string: MagicMock,
) -> None:
    """Test the basic binary sensor."""
    sensor = await _async_build_sensor(SENSOR_DATA, USER_INPUT)

    # On the assumed date, today is not a holiday and it is a work day, but something
    # went wrong getting the day of the week
    assert sensor.state == STATE_OFF


async def test_binary_sensor_duplicate_entry(hass: HomeAssistant) -> None:
    """Test that only one sensor of each name can be added."""
    with patch(
        "homeassistant.components.workday.util.get_date",
        return_value=ASSUMED_DATE,
    ), patch(
        "homeassistant.components.workday.binary_sensor.get_date",
        return_value=ASSUMED_DATE,
    ):
        added_result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=SENSOR_DATA,
        )
        second_result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=SENSOR_DATA,
        )

    assert added_result.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert added_result.get("data", {}) == SENSOR_DATA
    assert second_result.get("type") == data_entry_flow.FlowResultType.ABORT

    # Based on the input given, this should be the entity ID in use
    entity_id = "binary_sensor.workday_sensor"

    assert hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN) == [entity_id]

    sensor: State | None = hass.states.get(entity_id)
    assert sensor is not None
    assert sensor.state == STATE_ON


async def test_update_nonexistent_sensor(hass: HomeAssistant) -> None:
    """Test that calling update_listener on a fake entity doesn't fail."""
    entry = MockConfigEntry(
        domain=DOMAIN, entry_id="i-do-not-exist", unique_id="fake-sensor"
    )
    hass.data.setdefault(DOMAIN, {"i-do-exist": "hello-world"})
    await update_listener(hass, entry)
