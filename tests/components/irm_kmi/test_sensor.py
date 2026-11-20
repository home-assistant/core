"""Tests for the IRM KMI sensor platform."""

from collections.abc import Callable, Generator
from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from irm_kmi_api import (
    CurrentWeatherData,
    IrmKmiApiError,
    PollenLevel,
    PollenName,
    PollenParser,
    RadarForecast,
)
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import (
    ALDER_POLLEN_ENTITY_ID,
    CURRENT_WEATHER,
    POLLEN,
    RADAR_FORECAST,
    RAINFALL_ENTITY_ID,
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
async def test_pollen_unavailable_until_next_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_irm_kmi_api: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a pollen failure only makes the pollen sensors unavailable."""
    await setup_integration(hass, mock_config_entry)

    mock_irm_kmi_api.get_pollen.side_effect = IrmKmiApiError
    mock_irm_kmi_api.get_current_weather.return_value = CurrentWeatherData(
        **{**CURRENT_WEATHER, "temperature": 9.9}
    )

    freezer.tick(timedelta(minutes=8))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ALDER_POLLEN_ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get(TEMPERATURE_ENTITY_ID).state == "9.9"

    mock_irm_kmi_api.get_pollen.side_effect = None

    freezer.tick(timedelta(minutes=8))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ALDER_POLLEN_ENTITY_ID).state == PollenLevel.GREEN


@pytest.mark.freeze_time("2023-12-28T15:30:00+01:00")
async def test_pollen_kept_when_forecasts_fail(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_irm_kmi_api: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a forecast failure does not touch the pollen sensors."""
    await setup_integration(hass, mock_config_entry)

    mock_irm_kmi_api.refresh_forecasts_coord.side_effect = IrmKmiApiError
    mock_irm_kmi_api.get_pollen.return_value = {
        **POLLEN,
        PollenName.ALDER: PollenLevel.RED,
    }

    # Beyond the grace period of the weather data
    for _ in range(3):
        freezer.tick(timedelta(minutes=8))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(TEMPERATURE_ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get(ALDER_POLLEN_ENTITY_ID).state == PollenLevel.RED


@pytest.mark.parametrize(
    ("now", "radar_forecast", "expected_state"),
    [
        pytest.param(
            "2023-12-28T15:00:00+01:00",
            RADAR_FORECAST,
            "0.6",
            id="before_the_first_frame",
        ),
        pytest.param(
            "2023-12-28T15:10:00+01:00",
            RADAR_FORECAST,
            "0.6",
            id="on_the_first_frame",
        ),
        pytest.param(
            "2023-12-28T15:19:59+01:00",
            RADAR_FORECAST,
            "0.6",
            id="one_second_before_the_next_frame",
        ),
        pytest.param(
            "2023-12-28T15:20:00+01:00",
            RADAR_FORECAST,
            "0.3",
            id="on_a_frame",
        ),
        pytest.param(
            "2023-12-28T15:35:00+01:00",
            RADAR_FORECAST,
            "2.4",
            id="between_two_frames",
        ),
        pytest.param(
            "2023-12-28T16:30:00+01:00",
            RADAR_FORECAST,
            "7.2",
            id="after_the_last_frame",
        ),
        pytest.param(
            "2023-12-28T15:30:00+01:00",
            [],
            STATE_UNKNOWN,
            id="without_any_frame",
        ),
    ],
)
async def test_rainfall_frame_covering_now(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_irm_kmi_api: MagicMock,
    freezer: FrozenDateTimeFactory,
    now: str,
    radar_forecast: list[RadarForecast],
    expected_state: str,
) -> None:
    """Test the sensor reports the last radar frame that already started."""
    freezer.move_to(now)
    mock_irm_kmi_api.get_radar_forecast.return_value = radar_forecast

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(RAINFALL_ENTITY_ID)
    assert state
    assert state.state == expected_state


@pytest.mark.usefixtures("mock_get_forecasts_coord")
@pytest.mark.parametrize(
    ("forecast_fixture", "now", "expected_state"),
    [
        pytest.param(
            "forecast.json",
            "2023-12-26T18:15:00+01:00",
            "7.2",
            id="belgium",
        ),
        pytest.param(
            "forecast_nl_with_rain_on_radar.json",
            "2023-12-28T15:25:00+01:00",
            "0.15",
            id="netherlands",
        ),
    ],
)
async def test_rainfall_is_always_in_millimeters_per_hour(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    now: str,
    expected_state: str,
) -> None:
    """Test both units the provider reports are converted to mm/h."""
    freezer.move_to(now)

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(RAINFALL_ENTITY_ID)
    assert state
    assert state.state == expected_state
    assert (
        state.attributes[ATTR_UNIT_OF_MEASUREMENT]
        == UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR
    )


@pytest.mark.parametrize(
    "radar_forecast",
    [
        pytest.param(
            [RadarForecast(**{**RADAR_FORECAST[2], "unit": None})],
            id="without_a_unit",
        ),
        pytest.param(
            [RadarForecast(**{**RADAR_FORECAST[2], "unit": "mm/5min"})],
            id="unknown_unit",
        ),
        pytest.param(
            [RadarForecast(**{**RADAR_FORECAST[2], "native_precipitation": None})],
            id="without_a_rate",
        ),
    ],
)
@pytest.mark.freeze_time("2023-12-28T15:30:00+01:00")
async def test_rainfall_without_a_usable_frame(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_irm_kmi_api: MagicMock,
    radar_forecast: list[RadarForecast],
) -> None:
    """Test a frame that cannot be expressed in mm/h is unknown."""
    mock_irm_kmi_api.get_radar_forecast.return_value = radar_forecast

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(RAINFALL_ENTITY_ID)
    assert state
    assert state.state == STATE_UNKNOWN
