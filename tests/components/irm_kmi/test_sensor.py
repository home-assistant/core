"""Tests for the IRM KMI sensor platform."""

from collections.abc import Callable, Generator
from datetime import timedelta
import logging
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from irm_kmi_api import (
    CurrentWeatherData,
    IrmKmiApiError,
    PollenLevel,
    PollenName,
    PollenParser,
)
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import (
    ALDER_POLLEN_ENTITY_ID,
    CURRENT_WEATHER,
    TEMPERATURE_ENTITY_ID,
    WIND_DIRECTION_ENTITY_ID,
    WIND_GUST_SPEED_ENTITY_ID,
)


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Load only the sensor platform."""
    with patch("homeassistant.components.irm_kmi.PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_irm_kmi_api")
@pytest.mark.freeze_time("2023-12-28T15:30:00+01:00")
async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the state of every sensor."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_irm_kmi_api")
async def test_wind_gust_speed_disabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the wind gust speed sensor is disabled by default."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(WIND_GUST_SPEED_ENTITY_ID) is None
    entity_entry = entity_registry.async_get(WIND_GUST_SPEED_ENTITY_ID)
    assert entity_entry
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "entity_id",
    [
        "sensor.brussels_atmospheric_pressure",
        "sensor.brussels_uv_index",
        "sensor.brussels_wind_speed",
        WIND_DIRECTION_ENTITY_ID,
        WIND_GUST_SPEED_ENTITY_ID,
    ],
)
async def test_current_condition_sensor_without_its_key(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_irm_kmi_api: MagicMock,
    entity_id: str,
) -> None:
    """Test a current condition the API leaves out is unknown."""
    mock_irm_kmi_api.get_current_weather.return_value = CurrentWeatherData(
        condition="cloudy", temperature=7.2
    )

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    assert hass.states.get(TEMPERATURE_ENTITY_ID).state == "7.2"


@pytest.mark.parametrize(
    ("get_pollen_side_effect", "expected_state"),
    [
        pytest.param(
            PollenParser.get_default_data,
            PollenLevel.NONE,
            id="no_pollen_svg",
        ),
        pytest.param(
            IrmKmiApiError,
            STATE_UNAVAILABLE,
            id="api_error",
        ),
    ],
)
async def test_pollen_without_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_irm_kmi_api: MagicMock,
    get_pollen_side_effect: Callable[[], dict[PollenName, PollenLevel | None]]
    | type[Exception],
    expected_state: str,
) -> None:
    """Test the pollen level without a pollen SVG and when fetching it fails."""
    mock_irm_kmi_api.get_pollen.side_effect = get_pollen_side_effect

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ALDER_POLLEN_ENTITY_ID).state == expected_state
    assert hass.states.get(TEMPERATURE_ENTITY_ID).state == "7.2"


@pytest.mark.freeze_time("2023-12-28T15:30:00+01:00")
async def test_pollen_grace_period(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_irm_kmi_api: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the last pollen levels are only kept for the grace period."""
    await setup_integration(hass, mock_config_entry)

    assert "Pollen data is available again" not in caplog.text

    mock_irm_kmi_api.get_pollen.side_effect = IrmKmiApiError
    mock_irm_kmi_api.get_current_weather.return_value = CurrentWeatherData(
        **{**CURRENT_WEATHER, "temperature": 9.9}
    )

    freezer.tick(timedelta(minutes=8))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ALDER_POLLEN_ENTITY_ID).state == PollenLevel.GREEN
    assert hass.states.get(TEMPERATURE_ENTITY_ID).state == "9.9"

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ALDER_POLLEN_ENTITY_ID).state == STATE_UNAVAILABLE
    assert [
        record.levelno
        for record in caplog.records
        if record.message.startswith("Could not get pollen data from the API")
    ] == [logging.INFO]

    mock_irm_kmi_api.get_pollen.side_effect = None

    freezer.tick(timedelta(minutes=8))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ALDER_POLLEN_ENTITY_ID).state == PollenLevel.GREEN
    assert caplog.text.count("Pollen data is available again") == 1

    freezer.tick(timedelta(minutes=8))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert caplog.text.count("Pollen data is available again") == 1

    mock_irm_kmi_api.get_pollen.side_effect = IrmKmiApiError

    freezer.tick(timedelta(minutes=8))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert caplog.text.count("Could not get pollen data from the API") == 2


@pytest.mark.freeze_time("2023-12-28T15:30:00+01:00")
async def test_pollen_grace_period_when_forecasts_fail(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_irm_kmi_api: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test old weather data does not keep pollen beyond its grace period."""
    await setup_integration(hass, mock_config_entry)

    mock_irm_kmi_api.get_pollen.side_effect = IrmKmiApiError
    mock_irm_kmi_api.get_current_weather.return_value = CurrentWeatherData(
        **{**CURRENT_WEATHER, "temperature": 9.9}
    )

    freezer.tick(timedelta(minutes=8))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ALDER_POLLEN_ENTITY_ID).state == PollenLevel.GREEN

    mock_irm_kmi_api.refresh_forecasts_coord.side_effect = IrmKmiApiError

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ALDER_POLLEN_ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get(TEMPERATURE_ENTITY_ID).state == "9.9"


@pytest.mark.freeze_time("2023-12-28T15:30:00+01:00")
async def test_pollen_grace_period_after_processing_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_irm_kmi_api: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test pollen from an update that failed does not extend the grace period."""
    await setup_integration(hass, mock_config_entry)

    mock_irm_kmi_api.get_current_weather.side_effect = ValueError

    freezer.tick(timedelta(minutes=8))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(TEMPERATURE_ENTITY_ID).state == STATE_UNAVAILABLE

    mock_irm_kmi_api.get_current_weather.side_effect = None
    mock_irm_kmi_api.get_pollen.side_effect = IrmKmiApiError

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ALDER_POLLEN_ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get(TEMPERATURE_ENTITY_ID).state == "7.2"
