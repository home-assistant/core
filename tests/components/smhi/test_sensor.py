"""Test for the smhi weather entity."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pysmhi import SmhiFireForecastException, SMHIForecast
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "load_platforms",
    [[Platform.SENSOR]],
)
async def test_sensor_setup(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    load_int: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for successfully setting up the smhi sensors."""

    await snapshot_platform(hass, entity_registry, snapshot, load_int.entry_id)


@pytest.mark.usefixtures("load_int")
@pytest.mark.parametrize(
    "load_platforms",
    [[Platform.SENSOR]],
)
@pytest.mark.parametrize(
    ("key", "value", "entity_id", "expected_state"),
    [
        pytest.param(
            "thunder",
            150,
            "sensor.test_thunder_probability",
            "0",
            id="percentage_out_of_range",
        ),
        pytest.param(
            "thunder",
            None,
            "sensor.test_thunder_probability",
            STATE_UNKNOWN,
            id="percentage_missing",
        ),
        pytest.param(
            "precipitation_category",
            99,
            "sensor.test_precipitation_category",
            STATE_UNKNOWN,
            id="unknown_precipitation_category",
        ),
    ],
)
async def test_sensor_unexpected_values(
    hass: HomeAssistant,
    mock_client: MagicMock,
    get_data: tuple[list[SMHIForecast], list[SMHIForecast], list[SMHIForecast]],
    freezer: FrozenDateTimeFactory,
    key: str,
    value: int | None,
    entity_id: str,
    expected_state: str,
) -> None:
    """Test sensors handle unexpected values from the API."""
    daily = get_data[0]
    mock_client.async_get_daily_forecast.return_value = [
        {**daily[0], key: value},
        *daily[1:],
    ]
    freezer.tick(timedelta(minutes=35))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == expected_state


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "load_int")
@pytest.mark.parametrize(
    "load_platforms",
    [[Platform.SENSOR]],
)
async def test_fire_sensor_unavailable(
    hass: HomeAssistant,
    mock_fire_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test fire sensors become unavailable when the fire forecast fails."""
    entity_id = "sensor.test_fire_weather_index"

    mock_fire_client.async_get_daily_forecast.side_effect = SmhiFireForecastException(
        "boom"
    )
    freezer.tick(timedelta(minutes=35))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE

    mock_fire_client.async_get_daily_forecast.side_effect = None
    freezer.tick(timedelta(minutes=35))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "6.6"
