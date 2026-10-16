"""Test weather conditions."""

from datetime import datetime, timedelta
from typing import Any, cast

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.recorder import Recorder
from homeassistant.components.weather import (
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    DOMAIN,
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.components.weather.condition import CONDITIONS
from homeassistant.const import (
    ATTR_LABEL_ID,
    CONF_ENTITY_ID,
    STATE_UNAVAILABLE,
    UnitOfPrecipitationDepth,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConditionError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.condition import ConditionChecker
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import setup_test_component_platform
from tests.components.common import (
    TargetSupport,
    assert_condition_options_supported,
    assert_conditions_target_support,
    create_target_condition,
)
from tests.components.recorder.common import async_wait_recording_done

ENTITY_ID = "weather.home"
OTHER_ENTITY_ID = "weather.other"
START = datetime(2026, 10, 16, 6, 30, tzinfo=dt_util.UTC)

_CONDITION_TARGET_SUPPORT: dict[str, TargetSupport] = {
    "did_rain": TargetSupport.CUSTOM,
    "will_rain": TargetSupport.CUSTOM,
}


class RainWeather(WeatherEntity):
    """Weather entity with settable forecasts."""

    _attr_condition = ATTR_CONDITION_SUNNY
    _attr_native_temperature = 20
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS

    def __init__(
        self,
        entity_id: str,
        *,
        hourly: list[Forecast] | None = None,
        daily: list[Forecast] | None = None,
    ) -> None:
        """Initialize the entity."""
        self.entity_id = entity_id
        self._attr_unique_id = entity_id
        self.hourly = hourly
        self.daily = daily
        self._attr_supported_features = WeatherEntityFeature(0)
        if hourly is not None:
            self._attr_supported_features |= WeatherEntityFeature.FORECAST_HOURLY
        if daily is not None:
            self._attr_supported_features |= WeatherEntityFeature.FORECAST_DAILY

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast."""
        return self.hourly

    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast."""
        return self.daily


def _forecast(
    start: datetime, period: timedelta, values: list[tuple[float | None, int | None]]
) -> list[Forecast]:
    """Return forecast entries with (precipitation, probability) values."""
    return [
        {
            "datetime": (start + index * period).isoformat(),
            "native_precipitation": precipitation,
            "precipitation_probability": probability,
        }
        for index, (precipitation, probability) in enumerate(values)
    ]


async def _setup_entities(hass: HomeAssistant, *entities: RainWeather) -> None:
    """Set up weather entities."""
    setup_test_component_platform(hass, DOMAIN, entities)
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"platform": "test"}})
    await hass.async_block_till_done()


async def _create_condition(
    hass: HomeAssistant,
    condition: str,
    options: dict[str, Any],
    entity_ids: list[str] | None = None,
    behavior: str = "any",
) -> ConditionChecker:
    """Create a weather condition."""
    return cast(
        ConditionChecker,
        await create_target_condition(
            hass,
            condition=condition,
            target={CONF_ENTITY_ID: entity_ids or [ENTITY_ID]},
            behavior=behavior,
            condition_options=options,
        ),
    )


def _set_states(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_id: str,
    states: list[tuple[str, timedelta]],
) -> None:
    """Set each state of an entity, then move the time forward."""
    for state, duration in states:
        hass.states.async_set(entity_id, state)
        freezer.tick(duration)


@pytest.mark.parametrize(
    ("condition_key", "base_options"),
    [
        ("weather.did_rain", {"within": {"hours": 24}}),
        ("weather.will_rain", {"within": {"days": 2}, "threshold": 2}),
    ],
)
async def test_weather_condition_options_validation(
    hass: HomeAssistant, condition_key: str, base_options: dict[str, Any]
) -> None:
    """Test that weather conditions support the expected options."""
    await assert_condition_options_supported(
        hass,
        condition_key,
        base_options,
        supports_behavior=True,
        supports_duration=False,
    )


def test_condition_target_support() -> None:
    """Certify the condition registry matches its declared target support."""
    assert_conditions_target_support(CONDITIONS, _CONDITION_TARGET_SUPPORT)


@pytest.mark.parametrize(
    ("condition_key", "options"),
    [
        ("weather.did_rain", {"within": {"hours": 1}}),
        ("weather.will_rain", {"within": {"hours": 1}, "threshold": 1}),
    ],
)
async def test_sync_check_not_supported(
    hass: HomeAssistant, condition_key: str, options: dict[str, Any]
) -> None:
    """Test that a check that cannot fetch data raises an error."""
    hass.states.async_set(ENTITY_ID, ATTR_CONDITION_RAINY)
    test = await _create_condition(hass, condition_key, options)
    assert test.needs_polling is True

    with pytest.raises(ConditionError, match="cannot be checked here"):
        test.async_check()


@pytest.mark.parametrize(
    "condition",
    [
        ATTR_CONDITION_RAINY,
        ATTR_CONDITION_POURING,
        ATTR_CONDITION_LIGHTNING_RAINY,
        ATTR_CONDITION_SNOWY_RAINY,
    ],
)
async def test_did_rain_rainy_now(hass: HomeAssistant, condition: str) -> None:
    """Test that the condition passes while it rains, without history."""
    hass.states.async_set(ENTITY_ID, condition)
    test = await _create_condition(hass, "weather.did_rain", {"within": {"hours": 1}})
    assert await test.async_evaluate() is True


async def test_did_rain_no_recorder(hass: HomeAssistant) -> None:
    """Test that past rain cannot be checked without the recorder."""
    hass.states.async_set(ENTITY_ID, ATTR_CONDITION_SUNNY)
    test = await _create_condition(hass, "weather.did_rain", {"within": {"hours": 1}})
    with pytest.raises(ConditionError, match="recorder is not available"):
        await test.async_evaluate()


@pytest.mark.parametrize(
    ("states", "expected"),
    [
        pytest.param(
            [
                (ATTR_CONDITION_RAINY, timedelta(hours=1)),
                (ATTR_CONDITION_SUNNY, timedelta(hours=4)),
            ],
            True,
            id="rain_in_window",
        ),
        pytest.param(
            [
                (ATTR_CONDITION_RAINY, timedelta(hours=1)),
                (ATTR_CONDITION_SUNNY, timedelta(hours=7)),
            ],
            False,
            id="rain_before_window",
        ),
        pytest.param(
            [
                (ATTR_CONDITION_POURING, timedelta(hours=10)),
                (ATTR_CONDITION_SUNNY, timedelta(hours=1)),
            ],
            True,
            id="rain_at_window_start",
        ),
        pytest.param(
            [
                (ATTR_CONDITION_CLOUDY, timedelta(hours=1)),
                (ATTR_CONDITION_SNOWY, timedelta(hours=1)),
                (ATTR_CONDITION_SUNNY, timedelta(hours=1)),
            ],
            False,
            id="no_rain",
        ),
    ],
)
async def test_did_rain_from_history(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    states: list[tuple[str, timedelta]],
    expected: bool,
) -> None:
    """Test that the condition reads past rain from recorder history."""
    freezer.move_to(START)
    hass.states.async_set(ENTITY_ID, ATTR_CONDITION_CLOUDY)
    freezer.tick(timedelta(hours=1))
    _set_states(hass, freezer, ENTITY_ID, states)
    await async_wait_recording_done(hass)

    test = await _create_condition(hass, "weather.did_rain", {"within": {"hours": 6}})
    assert await test.async_evaluate() is expected


@pytest.mark.parametrize(("behavior", "expected"), [("any", True), ("all", False)])
async def test_did_rain_behavior(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    behavior: str,
    expected: bool,
) -> None:
    """Test the any and all behaviors."""
    freezer.move_to(START)
    hass.states.async_set(OTHER_ENTITY_ID, ATTR_CONDITION_SUNNY)
    _set_states(
        hass,
        freezer,
        ENTITY_ID,
        [
            (ATTR_CONDITION_RAINY, timedelta(hours=1)),
            (ATTR_CONDITION_SUNNY, timedelta(hours=1)),
        ],
    )
    await async_wait_recording_done(hass)

    test = await _create_condition(
        hass,
        "weather.did_rain",
        {"within": {"hours": 6}},
        [ENTITY_ID, OTHER_ENTITY_ID],
        behavior,
    )
    assert await test.async_evaluate() is expected

    hass.states.async_set(OTHER_ENTITY_ID, ATTR_CONDITION_POURING)
    assert await test.async_evaluate() is True


async def test_did_rain_skips_unavailable(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test that unavailable entities are skipped."""
    hass.states.async_set(ENTITY_ID, ATTR_CONDITION_RAINY)
    hass.states.async_set(OTHER_ENTITY_ID, STATE_UNAVAILABLE)
    test = await _create_condition(
        hass,
        "weather.did_rain",
        {"within": {"hours": 6}},
        [ENTITY_ID, OTHER_ENTITY_ID],
        "all",
    )
    assert await test.async_evaluate() is True


async def test_did_rain_label_target(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that the condition resolves indirect targets."""
    entity_registry.async_get_or_create(
        DOMAIN, "test", "home", suggested_object_id="home"
    )
    entity_registry.async_update_entity(ENTITY_ID, labels={"garden"})
    hass.states.async_set(ENTITY_ID, ATTR_CONDITION_RAINY)
    test = cast(
        ConditionChecker,
        await create_target_condition(
            hass,
            condition="weather.did_rain",
            target={ATTR_LABEL_ID: "garden"},
            behavior="any",
            condition_options={"within": {"hours": 1}},
        ),
    )
    assert await test.async_evaluate() is True

    entity_registry.async_update_entity(ENTITY_ID, labels=set())
    assert await test.async_evaluate() is False


@pytest.mark.parametrize(
    ("within", "threshold", "expected"),
    [
        ({"hours": 2}, 4, True),
        ({"hours": 2}, 4.1, False),
        ({"hours": 3}, 6, True),
        ({"minutes": 30}, 1, True),
        ({"minutes": 30}, 1.1, False),
    ],
)
async def test_will_rain_amount_hourly(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    within: dict[str, int],
    threshold: float,
    expected: bool,
) -> None:
    """Test the amount of rain in the hourly forecast."""
    freezer.move_to(START)
    # The first entry started 30 minutes ago.
    hourly = _forecast(
        START - timedelta(minutes=30),
        timedelta(hours=1),
        [(2, None), (2, None), (2, None), (2, None)],
    )
    await _setup_entities(hass, RainWeather(ENTITY_ID, hourly=hourly))
    test = await _create_condition(
        hass, "weather.will_rain", {"within": within, "threshold": threshold}
    )
    assert await test.async_evaluate() is expected


@pytest.mark.parametrize(
    ("within", "threshold", "expected"),
    [
        ({"hours": 3}, 50, True),
        ({"hours": 3}, 51, False),
        ({"hours": 4}, 80, True),
    ],
)
async def test_will_rain_probability(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    within: dict[str, int],
    threshold: float,
    expected: bool,
) -> None:
    """Test the probability of rain in the hourly forecast."""
    freezer.move_to(START)
    hourly = _forecast(
        START, timedelta(hours=1), [(None, 10), (None, 50), (None, None), (None, 80)]
    )
    await _setup_entities(hass, RainWeather(ENTITY_ID, hourly=hourly))
    test = await _create_condition(
        hass,
        "weather.will_rain",
        {"within": within, "measure": "probability", "threshold": threshold},
    )
    assert await test.async_evaluate() is expected


@pytest.mark.parametrize(
    ("within", "threshold", "expected"),
    [
        # Covered by the hourly forecast: 2 hours of 1 mm.
        ({"hours": 2}, 2, True),
        ({"hours": 2}, 2.1, False),
        # Not covered by the hourly forecast: 1.5 days of 10 mm per day.
        ({"days": 1, "hours": 12}, 15, True),
        ({"days": 1, "hours": 12}, 15.1, False),
        # Not covered by any forecast: the daily forecast reaches furthest.
        ({"days": 5}, 30, True),
        ({"days": 5}, 30.1, False),
    ],
)
async def test_will_rain_forecast_type(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    within: dict[str, int],
    threshold: float,
    expected: bool,
) -> None:
    """Test that the finest forecast that covers the window is used."""
    freezer.move_to(START)
    hourly = _forecast(START, timedelta(hours=1), [(1, None)] * 12)
    daily = _forecast(START, timedelta(days=1), [(10, None)] * 3)
    await _setup_entities(hass, RainWeather(ENTITY_ID, hourly=hourly, daily=daily))
    test = await _create_condition(
        hass, "weather.will_rain", {"within": within, "threshold": threshold}
    )
    assert await test.async_evaluate() is expected


async def test_will_rain_fetches_forecast(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test that each check fetches the current forecast."""
    freezer.move_to(START)
    entity = RainWeather(ENTITY_ID, hourly=[], daily=[])
    await _setup_entities(hass, entity)
    test = await _create_condition(
        hass, "weather.will_rain", {"within": {"hours": 2}, "threshold": 1}
    )
    assert await test.async_evaluate() is False

    entity.hourly = _forecast(START, timedelta(hours=1), [(1, None), (1, None)])
    assert await test.async_evaluate() is True


async def test_will_rain_unit(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the amount uses the precipitation unit of the entity."""
    freezer.move_to(START)
    entity = RainWeather(
        ENTITY_ID, hourly=_forecast(START, timedelta(hours=1), [(25.4, None)])
    )
    await _setup_entities(hass, entity)
    entity_registry.async_update_entity_options(
        ENTITY_ID, DOMAIN, {"precipitation_unit": UnitOfPrecipitationDepth.INCHES}
    )
    await hass.async_block_till_done()

    test = await _create_condition(
        hass, "weather.will_rain", {"within": {"hours": 1}, "threshold": 1}
    )
    assert await test.async_evaluate() is True
    test = await _create_condition(
        hass, "weather.will_rain", {"within": {"hours": 1}, "threshold": 1.1}
    )
    assert await test.async_evaluate() is False


@pytest.mark.parametrize(("behavior", "expected"), [("any", False), ("all", True)])
async def test_will_rain_no_forecast(
    hass: HomeAssistant, behavior: str, expected: bool
) -> None:
    """Test that entities without a forecast are skipped."""
    await _setup_entities(
        hass,
        RainWeather(ENTITY_ID),
        RainWeather(OTHER_ENTITY_ID, hourly=None, daily=[]),
    )
    test = await _create_condition(
        hass,
        "weather.will_rain",
        {"within": {"hours": 1}, "threshold": 0},
        [ENTITY_ID, OTHER_ENTITY_ID],
        behavior,
    )
    assert await test.async_evaluate() is expected


@pytest.mark.parametrize(("behavior", "expected"), [("any", False), ("all", True)])
async def test_will_rain_no_entity(
    hass: HomeAssistant, behavior: str, expected: bool
) -> None:
    """Test a state without a weather entity object."""
    hass.states.async_set(ENTITY_ID, ATTR_CONDITION_RAINY)
    test = await _create_condition(
        hass,
        "weather.will_rain",
        {"within": {"hours": 1}, "threshold": 0},
        behavior=behavior,
    )
    assert await test.async_evaluate() is expected

    await _setup_entities(hass)
    assert await test.async_evaluate() is expected
