"""Test the Foreca weather platform."""

from datetime import date
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyforeca import DailyForecast, ForecaConnectionError, ForecaError, HourlyForecast
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.foreca.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.components.foreca.services import (
    ForecaService,
    ForecaServiceArgument,
)
from homeassistant.components.weather import (
    DOMAIN as WEATHER_DOMAIN,
    SERVICE_GET_FORECASTS,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)

from . import init_integration

ENTITY_ID = "weather.helsinki"


@pytest.mark.usefixtures("mock_foreca_client")
async def test_weather(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the state of the weather entity."""
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.WEATHER]):
        await init_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_foreca_client")
@pytest.mark.parametrize("forecast_type", ["daily", "hourly"])
async def test_forecast(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    forecast_type: str,
) -> None:
    """Test the daily and hourly forecasts."""
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.WEATHER]):
        await init_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {ATTR_ENTITY_ID: ENTITY_ID, "type": forecast_type},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


@pytest.mark.parametrize(
    ("forecast_type", "mocked_method", "undated"),
    [
        ("daily", "forecast_daily", [DailyForecast(date=None)]),
        ("hourly", "forecast_hourly", [HourlyForecast(time=None)]),
    ],
)
async def test_forecast_without_a_time_is_dropped(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
    forecast_type: str,
    mocked_method: str,
    undated: list[DailyForecast] | list[HourlyForecast],
) -> None:
    """Test that a forecast entry without a date or time is left out."""
    getattr(mock_foreca_client, mocked_method).return_value = undated
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.WEATHER]):
        await init_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {ATTR_ENTITY_ID: ENTITY_ID, "type": forecast_type},
        blocking=True,
        return_response=True,
    )
    assert response == {ENTITY_ID: {"forecast": []}}


@pytest.mark.usefixtures("mock_foreca_client")
async def test_daily_forecast_lands_on_the_right_local_day(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a daily forecast keeps its date in a timezone west of UTC.

    Anchoring to midnight UTC would put the forecast on the previous day for
    anyone west of it.
    """
    await hass.config.async_set_time_zone("America/Los_Angeles")
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.WEATHER]):
        await init_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {ATTR_ENTITY_ID: ENTITY_ID, "type": "daily"},
        blocking=True,
        return_response=True,
    )
    first = response[ENTITY_ID]["forecast"][0]
    timestamp = dt_util.parse_datetime(first["datetime"])
    assert timestamp is not None
    # The date has to survive being rendered where Home Assistant is, which is
    # what midnight UTC would break.
    assert dt_util.as_local(timestamp).date() == date(2026, 9, 2)


@pytest.mark.usefixtures("mock_foreca_client")
@pytest.mark.parametrize("forecast_type", ["daily", "hourly"])
@pytest.mark.parametrize(
    "unit_system",
    [
        pytest.param(METRIC_SYSTEM, id="metric"),
        pytest.param(US_CUSTOMARY_SYSTEM, id="us_customary"),
    ],
)
async def test_forecasts_extra(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    forecast_type: str,
    unit_system: UnitSystem,
) -> None:
    """Test the extra forecast values in the entity's units."""
    hass.config.units = unit_system
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.WEATHER]):
        await init_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        ForecaService.GET_FORECASTS_EXTRA,
        {ATTR_ENTITY_ID: ENTITY_ID, ForecaServiceArgument.TYPE: forecast_type},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


@pytest.mark.parametrize(
    ("forecast_type", "mocked_method", "undated"),
    [
        ("daily", "forecast_daily", [DailyForecast(date=None)]),
        ("hourly", "forecast_hourly", [HourlyForecast(time=None)]),
    ],
)
async def test_forecasts_extra_without_a_time_is_dropped(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
    forecast_type: str,
    mocked_method: str,
    undated: list[DailyForecast] | list[HourlyForecast],
) -> None:
    """Test that a forecast entry without a date or time is left out."""
    getattr(mock_foreca_client, mocked_method).return_value = undated
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.WEATHER]):
        await init_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        ForecaService.GET_FORECASTS_EXTRA,
        {ATTR_ENTITY_ID: ENTITY_ID, ForecaServiceArgument.TYPE: forecast_type},
        blocking=True,
        return_response=True,
    )
    assert response == {ENTITY_ID: {"forecast": []}}


async def test_forecasts_extra_fails_while_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the action raises instead of returning stale data after a failed update."""
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.WEATHER]):
        await init_integration(hass, mock_config_entry)

    mock_foreca_client.current.side_effect = ForecaConnectionError
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            ForecaService.GET_FORECASTS_EXTRA,
            {ATTR_ENTITY_ID: ENTITY_ID, ForecaServiceArgument.TYPE: "daily"},
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize(
    "unit_system",
    [
        pytest.param(METRIC_SYSTEM, id="metric"),
        pytest.param(US_CUSTOMARY_SYSTEM, id="us_customary"),
    ],
)
async def test_3_hour_forecast(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
    unit_system: UnitSystem,
) -> None:
    """Test the 3-hour forecast covers 14 days in the entity's units."""
    hass.config.units = unit_system
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.WEATHER]):
        await init_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        ForecaService.GET_3_HOUR_FORECAST,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot
    assert mock_foreca_client.forecast_3hourly.await_args.kwargs == {
        "periods": 112,
        "dataset": "full",
        "rounding": 0,
    }


async def test_3_hour_forecast_without_a_time_is_dropped(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
) -> None:
    """Test that a 3-hour step without a time is left out."""
    mock_foreca_client.forecast_3hourly.return_value = [HourlyForecast(time=None)]
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.WEATHER]):
        await init_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        ForecaService.GET_3_HOUR_FORECAST,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
        return_response=True,
    )
    assert response == {ENTITY_ID: {"forecast": []}}


async def test_3_hour_forecast_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
) -> None:
    """Test a failed 3-hour forecast request raises a translated error."""
    mock_foreca_client.forecast_3hourly.side_effect = ForecaError("timeout")
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.WEATHER]):
        await init_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            ForecaService.GET_3_HOUR_FORECAST,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
            return_response=True,
        )
    assert exc_info.value.translation_key == "three_hour_forecast_error"
    assert str(exc_info.value) == "Error fetching the 3-hour forecast"
