"""Test the GeoSphere Austria Forecast weather platform."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from pytest_homeassistant.typing import WebSocketGenerator
from syrupy.assertion import SnapshotAssertion
from zamg import ZamgApiError

from homeassistant.components.weather import (
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_WIND_GUST_SPEED,
    DOMAIN as WEATHER_DOMAIN,
    SERVICE_GET_FORECASTS,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

ENTITY_ID = "weather.pixendorf"


@pytest.mark.usefixtures("mock_nwp_client")
async def test_weather(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the state of the weather entity."""
    await init_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_nwp_client")
async def test_hourly_forecast(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the hourly forecast starts with the hour in progress."""
    await init_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {ATTR_ENTITY_ID: ENTITY_ID, "type": "hourly"},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


@pytest.mark.parametrize(
    ("now", "state", "temperature", "wind_gust_speed"),
    [
        pytest.param("2026-09-26T05:00:00+00:00", "sunny", 10.0, 28.8, id="first_hour"),
        pytest.param("2026-09-26T05:59:00+00:00", "sunny", 10.0, 28.8, id="late"),
        pytest.param("2026-09-26T06:00:00+00:00", "sunny", 11.0, 34.2, id="full_hour"),
        pytest.param(
            "2026-09-26T04:59:00+00:00", STATE_UNKNOWN, None, 27.0, id="before"
        ),
        pytest.param(
            "2026-09-26T13:00:00+00:00", STATE_UNKNOWN, None, None, id="after"
        ),
    ],
)
@pytest.mark.usefixtures("mock_nwp_client")
async def test_current_hour(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    now: str,
    state: str,
    temperature: float | None,
    wind_gust_speed: float | None,
) -> None:
    """Test the state comes from the current hour and gusts from the hour in progress."""
    freezer.move_to(now)
    await init_integration(hass, mock_config_entry)

    entity = hass.states.get(ENTITY_ID)
    assert entity is not None
    assert entity.state == state
    assert entity.attributes.get(ATTR_WEATHER_TEMPERATURE) == temperature
    assert entity.attributes.get(ATTR_WEATHER_WIND_GUST_SPEED) == wind_gust_speed


async def test_next_hour_without_request(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_nwp_client: MagicMock,
) -> None:
    """Test the state moves to the next record at the full hour."""
    freezer.move_to("2026-09-26T05:46:00+00:00")
    await init_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).attributes[ATTR_WEATHER_TEMPERATURE] == 10.0

    freezer.move_to("2026-09-26T06:00:00+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).attributes[ATTR_WEATHER_TEMPERATURE] == 11.0
    assert mock_nwp_client.get_forecast.await_count == 1


async def test_forecast_subscription_moves_at_full_hour(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_nwp_client: MagicMock,
) -> None:
    """Test forecast subscribers get the shorter forecast at the full hour."""
    await init_integration(hass, mock_config_entry)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "weather/subscribe_forecast",
            "forecast_type": "hourly",
            "entity_id": ENTITY_ID,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    msg = await client.receive_json()
    assert msg["event"]["forecast"][0]["datetime"] == "2026-09-26T06:00:00+00:00"

    freezer.move_to("2026-09-26T06:00:00+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    msg = await client.receive_json()
    assert msg["event"]["forecast"][0]["datetime"] == "2026-09-26T07:00:00+00:00"
    assert mock_nwp_client.get_forecast.await_count == 1


async def test_unavailable_then_recovers(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_nwp_client: MagicMock,
) -> None:
    """Test the entity is unavailable while updates fail."""
    await init_integration(hass, mock_config_entry)

    mock_nwp_client.get_forecast.side_effect = ZamgApiError("Error", status_code=500)
    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    mock_nwp_client.get_forecast.side_effect = None
    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    # 07:10 belongs to the record valid at 07:00.
    assert hass.states.get(ENTITY_ID).state == "partlycloudy"


async def test_rate_limit_retries_after_reset(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_nwp_client: MagicMock,
) -> None:
    """Test a rate-limited update is retried when the limit resets."""
    await init_integration(hass, mock_config_entry)

    mock_nwp_client.get_forecast.side_effect = ZamgApiError(
        "Too many requests", status_code=429, rate_limit_reset=600
    )
    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_nwp_client.get_forecast.await_count == 2

    mock_nwp_client.get_forecast.side_effect = None
    freezer.tick(timedelta(seconds=600))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_nwp_client.get_forecast.await_count == 3
    # 06:20 belongs to the record valid at 06:00.
    assert hass.states.get(ENTITY_ID).attributes[ATTR_WEATHER_TEMPERATURE] == 11.0
