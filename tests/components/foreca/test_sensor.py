"""Test the Foreca sensor platform."""

from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyforeca import (
    AirQualityForecast,
    CurrentWeather,
    ForecaAuthError,
    ForecaConnectionError,
    ForecaProductUnavailableError,
    Observation,
)
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_object_fixture,
    load_json_object_fixture,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.foreca.const import (
    DOMAIN,
    UPDATE_INTERVAL,
    symbol_to_condition,
)
from homeassistant.components.sensor import ATTR_LAST_RESET
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
    UnitOfLength,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from . import init_integration, load_observation

AIR_QUALITY_INDEX = "sensor.helsinki_air_quality_index"
HOURLY_PRECIPITATION = "sensor.helsinki_observed_hourly_precipitation"
OBSERVED_TEMPERATURE = "sensor.helsinki_observed_temperature"
PRECIPITATION_TYPE = "sensor.helsinki_observed_precipitation_type"
PRECIPITATION_3_HOURS = "sensor.helsinki_observed_3_hour_precipitation"
PRECIPITATION_6_HOURS = "sensor.helsinki_observed_6_hour_precipitation"
PRECIPITATION_12_HOURS = "sensor.helsinki_observed_12_hour_precipitation"
PRECIPITATION_24_HOURS = "sensor.helsinki_observed_24_hour_precipitation"


def _totals_at(city: str, time: str) -> Observation:
    """Return the totals of a city's station as if observed at another time."""
    station = load_json_object_fixture(
        f"observation_precipitation_totals_{city}.json", DOMAIN
    )["observations"][0]
    return Observation.from_api(station | {"time": time})


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_foreca_client")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the states of the sensors."""
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_foreca_client")
async def test_sensors_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test which sensors are disabled by default."""
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_config_entry)

    disabled = {
        entry.entity_id
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    }
    assert disabled == {
        "sensor.helsinki_carbon_monoxide_index",
        "sensor.helsinki_nitrogen_dioxide_index",
        "sensor.helsinki_ozone_index",
        "sensor.helsinki_pm10_index",
        "sensor.helsinki_pm2_5_index",
        "sensor.helsinki_sulphur_dioxide_index",
        PRECIPITATION_3_HOURS,
        PRECIPITATION_6_HOURS,
        PRECIPITATION_12_HOURS,
        "sensor.helsinki_observation_time",
        "sensor.helsinki_observed_apparent_temperature",
        "sensor.helsinki_observed_condition",
        "sensor.helsinki_observed_precipitation_type",
        "sensor.helsinki_observed_pressure",
        "sensor.helsinki_observed_snow_depth",
        "sensor.helsinki_observed_visibility",
        "sensor.helsinki_observed_wind_direction",
        "sensor.helsinki_observed_wind_gust_speed",
        "sensor.helsinki_observed_wind_speed",
    }


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("observation", "precipitation_totals", "air_quality"),
    [
        pytest.param(None, None, [], id="no_station_or_air_quality_nearby"),
        pytest.param(
            Observation(), Observation(), [AirQualityForecast()], id="empty_values"
        ),
    ],
)
async def test_sensors_without_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
    observation: Observation | None,
    air_quality: list[AirQualityForecast],
) -> None:
    """Test sensors are unknown when the API leaves their value out."""
    mock_foreca_client.current.return_value = CurrentWeather()
    mock_foreca_client.observation_latest.return_value = observation
    mock_foreca_client.air_quality_hourly.return_value = air_quality
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_config_entry)

    states = hass.states.async_all(Platform.SENSOR)
    assert len(states) == 29
    assert {state.state for state in states} == {STATE_UNKNOWN}


@pytest.mark.usefixtures("mock_foreca_client", "entity_registry_enabled_by_default")
async def test_observed_condition_options_cover_every_symbol(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test every Foreca symbol maps to one of the observed condition's options."""
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.helsinki_observed_condition")
    assert state is not None
    codes = [
        f"{day}{cloudiness}{rate}{kind}"
        for day in "dn"
        for cloudiness in range(7)
        for rate in range(5)
        for kind in range(3)
    ]
    assert {symbol_to_condition(code) for code in codes} <= set(
        state.attributes["options"]
    )


@pytest.mark.usefixtures("mock_foreca_client", "entity_registry_enabled_by_default")
async def test_observed_visibility_in_miles(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test observed visibility follows a US customary unit system."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.helsinki_observed_visibility")
    assert state is not None
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfLength.MILES
    assert float(state.state) == pytest.approx(12.43, abs=0.01)


def _unavailable(hass: HomeAssistant) -> set[str]:
    """Return the entities that are unavailable."""
    return {
        state.entity_id
        for state in hass.states.async_all()
        if state.state == STATE_UNAVAILABLE
    }


@pytest.mark.parametrize(
    ("method", "precipitation", "unavailable", "requests"),
    [
        pytest.param(
            "observation_latest",
            "hourly",
            {
                "sensor.helsinki_observation_station",
                HOURLY_PRECIPITATION,
                "sensor.helsinki_observed_humidity",
                OBSERVED_TEMPERATURE,
            },
            6,
            id="observation",
        ),
        pytest.param(
            "observation_latest",
            "latest",
            {PRECIPITATION_24_HOURS},
            6,
            id="precipitation_totals",
        ),
        pytest.param(
            "air_quality_hourly",
            None,
            {AIR_QUALITY_INDEX, "sensor.helsinki_dominant_pollutant"},
            3,
            id="air_quality",
        ),
    ],
)
async def test_failed_request_leaves_other_entities_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    method: str,
    precipitation: str | None,
    unavailable: set[str],
    requests: int,
) -> None:
    """Test a failing station or air quality request makes only its sensors unavailable.

    The station is asked twice per update, once for its hourly precipitation
    and once for its totals, and either request can fail on its own.
    """
    request = getattr(mock_foreca_client, method)
    respond = request.side_effect

    async def fail(location: str, **kwargs: Any) -> Any:
        if kwargs.get("precipitation") == precipitation:
            raise ForecaConnectionError("Timeout")
        return await respond(location, **kwargs)

    request.side_effect = fail
    await init_integration(hass, mock_config_entry)

    assert _unavailable(hass) == unavailable

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert _unavailable(hass) == unavailable

    request.side_effect = respond
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert _unavailable(hass) == set()
    assert request.await_count == requests


async def test_air_quality_update_error_is_translated(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failing air quality request logs the translated error."""
    mock_foreca_client.air_quality_hourly.side_effect = ForecaConnectionError("Timeout")
    await init_integration(hass, mock_config_entry)

    assert "Error fetching the air quality" in caplog.text


@pytest.mark.parametrize(
    ("method", "entity_id", "value"),
    [
        pytest.param(
            "observation_latest", OBSERVED_TEMPERATURE, "5.6", id="observation"
        ),
        pytest.param("air_quality_hourly", AIR_QUALITY_INDEX, "31", id="air_quality"),
    ],
)
async def test_rejected_key_on_a_sensor_request_keeps_the_entry_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    method: str,
    entity_id: str,
    value: str,
) -> None:
    """Test a key rejected only by a sensor request leaves the rest running.

    The request keeps being polled, so its sensors recover once the API
    accepts it again.
    """
    await init_integration(hass, mock_config_entry)

    getattr(mock_foreca_client, method).side_effect = ForecaAuthError
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    assert hass.states.get("weather.helsinki").state == "partlycloudy"

    getattr(mock_foreca_client, method).side_effect = None
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == value


async def test_observations_missing_from_plan_keep_the_entry_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
) -> None:
    """Test a plan without station observations loads and asks for no new key."""
    mock_foreca_client.observation_latest.side_effect = ForecaProductUnavailableError
    await init_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.config_entries.flow.async_progress() == []
    assert hass.states.get(OBSERVED_TEMPERATURE).state == STATE_UNAVAILABLE
    assert hass.states.get("weather.helsinki").state == "partlycloudy"


async def test_unknown_pollutant(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
) -> None:
    """Test a pollutant name outside the documented set reads as unknown."""
    mock_foreca_client.air_quality_hourly.return_value = [
        AirQualityForecast(pollutant="Pollen", aqi=12)
    ]
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.helsinki_dominant_pollutant").state == STATE_UNKNOWN
    assert hass.states.get(AIR_QUALITY_INDEX).state == "12"


async def test_observation_request(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
) -> None:
    """Test the station requests ask for precipitation and unrounded values.

    The API answers a request for both the hourly series and the totals with
    neither, so each needs a request of its own.
    """
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_config_entry)

    assert [
        call.kwargs for call in mock_foreca_client.observation_latest.await_args_list
    ] == [
        {"precipitation": "hourly", "rounding": 0},
        {"precipitation": "latest", "rounding": 0},
    ]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("fixture", "amount", "precipitation_type", "last_reset"),
    [
        pytest.param(
            "observation_hourly_precipitation_tromso.json",
            "0.3",
            "rain",
            "2026-11-06T12:00:00+01:00",
            id="rain",
        ),
        pytest.param(
            "observation_hourly_precipitation_zurich.json",
            "0",
            STATE_UNKNOWN,
            "2026-11-06T12:00:00+01:00",
            id="type_without_precipitation",
        ),
        pytest.param(
            "observation_hourly_precipitation_reykjavik.json",
            "0",
            STATE_UNKNOWN,
            "2026-11-06T10:00:00+00:00",
            id="last_hour_not_reported",
        ),
    ],
)
async def test_observed_hourly_precipitation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
    fixture: str,
    amount: str,
    precipitation_type: str,
    last_reset: str,
) -> None:
    """Test the station's last full hour of precipitation and its type.

    Zurich reports rain for an hour without precipitation. Reykjavik's newest
    hour ends an hour before its observation.
    """
    mock_foreca_client.observation_latest.return_value = load_observation(fixture)
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_config_entry)

    state = hass.states.get(HOURLY_PRECIPITATION)
    assert state is not None
    assert state.state == amount
    assert state.attributes[ATTR_LAST_RESET] == last_reset
    assert hass.states.get(PRECIPITATION_TYPE).state == precipitation_type


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("skipped_hours", "time", "amount", "precipitation_type"),
    [
        pytest.param(2, "2026-11-06T13:00:00+01:00", "0.7", "rain", id="two_hours"),
        pytest.param(
            3,
            "2026-11-06T13:00:00+01:00",
            STATE_UNKNOWN,
            STATE_UNKNOWN,
            id="3_12_and_24_hours",
        ),
        pytest.param(0, None, STATE_UNKNOWN, STATE_UNKNOWN, id="no_observation_time"),
    ],
)
async def test_stale_hourly_precipitation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
    skipped_hours: int,
    time: str | None,
    amount: str,
    precipitation_type: str,
) -> None:
    """Test the last hour is unknown once it is more than two hours old.

    The Tromso response stands in for a station that skipped its latest hours,
    with those hours left out of its series.
    """
    station = (
        await async_load_json_object_fixture(
            hass, "observation_hourly_precipitation_tromso.json", DOMAIN
        )
    )["observations"][0]
    hours = station["precip1h"]
    station["precip1h"] = hours[: len(hours) - skipped_hours]
    station["time"] = time
    mock_foreca_client.observation_latest.return_value = Observation.from_api(station)
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_config_entry)

    state = hass.states.get(HOURLY_PRECIPITATION)
    assert state is not None
    assert state.state == amount
    assert hass.states.get(PRECIPITATION_TYPE).state == precipitation_type


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_foreca_client")
@pytest.mark.parametrize(
    ("precipitation_totals", "expected"),
    [
        pytest.param(
            load_observation("observation_precipitation_totals_london.json"),
            {
                PRECIPITATION_3_HOURS: (STATE_UNKNOWN, None),
                PRECIPITATION_6_HOURS: ("0.8", "2026-11-06T06:00:00+00:00"),
                PRECIPITATION_12_HOURS: ("1.2", "2026-11-05T21:00:00+00:00"),
                PRECIPITATION_24_HOURS: ("0.4", "2026-11-05T06:00:00+00:00"),
            },
            id="6_12_and_24_hours",
        ),
        pytest.param(
            load_observation("observation_precipitation_totals_helsinki.json"),
            {
                PRECIPITATION_3_HOURS: (STATE_UNKNOWN, None),
                PRECIPITATION_6_HOURS: (STATE_UNKNOWN, None),
                PRECIPITATION_12_HOURS: (STATE_UNKNOWN, None),
                PRECIPITATION_24_HOURS: ("0", "2026-11-05T08:00:00+02:00"),
            },
            id="periods_not_reported",
        ),
        pytest.param(
            load_observation("observation_precipitation_totals_berlin.json"),
            {
                PRECIPITATION_3_HOURS: ("0", "2026-11-09T07:00:00+01:00"),
                PRECIPITATION_6_HOURS: (STATE_UNKNOWN, None),
                PRECIPITATION_12_HOURS: ("0", "2026-11-08T19:00:00+01:00"),
                PRECIPITATION_24_HOURS: ("0", "2026-11-08T07:00:00+01:00"),
            },
            id="3_12_and_24_hours",
        ),
        pytest.param(
            _totals_at("berlin", "2026-11-09T14:20:00+01:00"),
            {
                PRECIPITATION_3_HOURS: (STATE_UNKNOWN, None),
                PRECIPITATION_6_HOURS: (STATE_UNKNOWN, None),
                PRECIPITATION_12_HOURS: ("0", "2026-11-08T19:00:00+01:00"),
                PRECIPITATION_24_HOURS: ("0", "2026-11-08T07:00:00+01:00"),
            },
            id="3_hours_stale",
        ),
        pytest.param(
            _totals_at("london", "2026-11-06T19:00:00Z"),
            {
                PRECIPITATION_3_HOURS: (STATE_UNKNOWN, None),
                PRECIPITATION_6_HOURS: ("0.8", "2026-11-06T06:00:00+00:00"),
                PRECIPITATION_12_HOURS: ("1.2", "2026-11-05T21:00:00+00:00"),
                PRECIPITATION_24_HOURS: ("0.4", "2026-11-05T06:00:00+00:00"),
            },
            id="next_6_hours_an_hour_late",
        ),
        pytest.param(
            _totals_at("london", "2026-11-06T19:20:00Z"),
            {
                PRECIPITATION_3_HOURS: (STATE_UNKNOWN, None),
                PRECIPITATION_6_HOURS: (STATE_UNKNOWN, None),
                PRECIPITATION_12_HOURS: ("1.2", "2026-11-05T21:00:00+00:00"),
                PRECIPITATION_24_HOURS: ("0.4", "2026-11-05T06:00:00+00:00"),
            },
            id="6_hours_stale",
        ),
        pytest.param(
            _totals_at("london", "2026-11-07T07:20:00Z"),
            {
                PRECIPITATION_3_HOURS: (STATE_UNKNOWN, None),
                PRECIPITATION_6_HOURS: (STATE_UNKNOWN, None),
                PRECIPITATION_12_HOURS: (STATE_UNKNOWN, None),
                PRECIPITATION_24_HOURS: (STATE_UNKNOWN, None),
            },
            id="all_stale",
        ),
    ],
)
async def test_observed_precipitation_totals(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    expected: dict[str, tuple[str, str | None]],
) -> None:
    """Test the station's own totals and the windows they cover.

    A total counts until an hour after the next one should have ended.
    """
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_config_entry)

    states = {entity_id: hass.states.get(entity_id) for entity_id in expected}
    assert {
        entity_id: (state.state, state.attributes.get(ATTR_LAST_RESET))
        for entity_id, state in states.items()
        if state is not None
    } == expected
