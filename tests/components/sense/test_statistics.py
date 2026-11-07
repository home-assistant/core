"""Tests for the hourly statistics the Sense integration imports."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from sense_energy import SenseAPIException
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    StatisticsRow,
    async_import_statistics,
    get_metadata,
    statistics_during_period,
)
from homeassistant.components.sense.const import DOMAIN, TREND_UPDATE_MINUTES
from homeassistant.components.sense.statistics import WINDOW_HOURS
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DOMAIN as SENSOR_DOMAIN,
    SensorStateClass,
)
from homeassistant.const import CONF_ENTITIES, CONF_EXCLUDE, Platform, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import EnergyConverter

from . import setup_platform, trigger_trend_refresh
from .conftest import MockTrends
from .const import HOURLY_ENERGY, MONITOR_ID, PERIOD_TO_DATE

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done

# Every time sensitive test is pinned to this instant: one minute past the hour, so
# the window is the six completed hours 04:00 through 09:00.
NOW = "2026-01-15 10:01:00+00:00"

USAGE = f"sensor.sense_{MONITOR_ID}_daily_energy"
PRODUCTION = f"sensor.sense_{MONITOR_ID}_daily_production"
FROM_GRID = f"sensor.sense_{MONITOR_ID}_daily_from_grid"
TO_GRID = f"sensor.sense_{MONITOR_ID}_daily_to_grid"
NET_PRODUCTION = f"sensor.sense_{MONITOR_ID}_daily_net_production"
STATISTIC_SENSORS = [
    f"sensor.sense_{MONITOR_ID}_{scale}_{variant}"
    for scale in ("daily", "weekly", "monthly", "yearly", "bill")
    for variant in ("energy", "production", "from_grid", "to_grid")
]
# What the recorder is made to hold for an hour the import has not rewritten.
SEED_VALUE = 77.0
SCALE_USAGE_SENSORS = [
    USAGE,
    f"sensor.sense_{MONITOR_ID}_weekly_energy",
    f"sensor.sense_{MONITOR_ID}_monthly_energy",
    f"sensor.sense_{MONITOR_ID}_yearly_energy",
    f"sensor.sense_{MONITOR_ID}_bill_energy",
]


def window(now: str = NOW) -> list[datetime]:
    """Return the hours the import rewrites when run at now."""
    end = dt_util.parse_datetime(now).replace(minute=0, second=0, microsecond=0)
    return [end - timedelta(hours=offset) for offset in range(WINDOW_HOURS, 0, -1)]


def seed_metadata(
    entity_id: str, unit: str = UnitOfEnergy.KILO_WATT_HOUR
) -> StatisticMetaData:
    """Return metadata matching what the recorder compiles the sensors with."""
    return StatisticMetaData(
        mean_type=StatisticMeanType.NONE,
        has_sum=True,
        name=None,
        source="recorder",
        statistic_id=entity_id,
        unit_class=EnergyConverter.UNIT_CLASS,
        unit_of_measurement=unit,
    )


async def get_sums(hass: HomeAssistant, entity_id: str) -> list[float | None]:
    """Return the sum of every row held for the entity."""
    return [row["sum"] for row in (await get_stats(hass, [entity_id]))[entity_id]]


async def get_stats(
    hass: HomeAssistant, entity_ids: list[str], start: datetime | None = None
) -> dict[str, list[StatisticsRow]]:
    """Return every imported row for the given entities."""
    return await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        start or dt_util.parse_datetime("2026-01-01 00:00:00+00:00"),
        None,
        set(entity_ids),
        "hour",
        None,
        {"state", "sum"},
    )


async def seed_compiled_hour(hass: HomeAssistant, hour: datetime) -> None:
    """Add the row the recorder compiles for hour, for every sensor lacking one.

    Only hours the recorder has already compiled are rewritten.
    """
    existing = await get_stats(hass, STATISTIC_SENSORS, hour)
    for entity_id in STATISTIC_SENSORS:
        if entity_id not in existing:
            async_import_statistics(
                hass,
                seed_metadata(entity_id),
                [StatisticData(start=hour, state=SEED_VALUE, sum=SEED_VALUE)],
            )
    await async_wait_recording_done(hass)


async def setup_and_import(
    hass: HomeAssistant, config_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """Set up the sensor platform and wait for an import to land.

    The refresh during setup runs before the platform has registered its entities, so
    the statistics are written by the refresh after it.
    """
    await seed_compiled_hour(hass, window(str(dt_util.utcnow()))[-1])
    await setup_platform(hass, config_entry, Platform.SENSOR)
    await trigger_trend_refresh(hass, freezer)
    await async_wait_recording_done(hass)


async def test_imports_hourly_statistics(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test each completed hour is imported against the entity's own statistic ID."""
    freezer.move_to(NOW)
    await setup_and_import(hass, config_entry, freezer)

    stats = await get_stats(hass, [USAGE, PRODUCTION, FROM_GRID, TO_GRID])
    assert stats == snapshot

    rows = stats[USAGE]
    assert [row["start"] for row in rows] == [hour.timestamp() for hour in window()]
    assert [row["sum"] for row in rows] == pytest.approx(
        [HOURLY_ENERGY["usage"] * (index + 1) for index in range(WINDOW_HOURS)]
    )


async def test_current_hour_not_imported(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the in-progress hour is never written. Regression for #149492."""
    freezer.move_to("2026-01-15 01:30:00+00:00")
    await setup_and_import(hass, config_entry, freezer)

    rows = (await get_stats(hass, [USAGE], dt_util.utc_from_timestamp(0)))[USAGE]
    assert (
        rows[-1]["start"]
        == dt_util.parse_datetime("2026-01-15 00:00:00+00:00").timestamp()
    )


async def test_final_hour_of_day_imported(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the hour before midnight is not lost to the daily reset. Regression for #66077."""
    freezer.move_to("2026-01-15 00:30:00+00:00")
    await setup_and_import(hass, config_entry, freezer)

    rows = (await get_stats(hass, [USAGE], dt_util.utc_from_timestamp(0)))[USAGE]
    starts = [row["start"] for row in rows]
    assert dt_util.parse_datetime("2026-01-14 23:00:00+00:00").timestamp() in starts


async def test_all_scales_get_the_same_hourly_energy(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test every display scale reports the same energy for the hour."""
    freezer.move_to(NOW)
    await setup_and_import(hass, config_entry, freezer)

    stats = await get_stats(hass, SCALE_USAGE_SENSORS)
    assert set(stats) == set(SCALE_USAGE_SENSORS)
    daily = [row["sum"] for row in stats[USAGE]]
    for entity_id in SCALE_USAGE_SENSORS:
        assert [row["sum"] for row in stats[entity_id]] == pytest.approx(daily)


async def test_signed_and_percentage_sensors_are_not_imported(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test net production is left alone, since a negative hour would break the sum."""
    freezer.move_to(NOW)
    await setup_and_import(hass, config_entry, freezer)

    assert await get_stats(hass, [NET_PRODUCTION]) == {}


@pytest.mark.parametrize(
    "anchor_age",
    [
        pytest.param(timedelta(hours=1), id="adjacent_hour"),
        pytest.param(timedelta(days=120), id="long_outage"),
    ],
)
async def test_continues_existing_sum(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    anchor_age: timedelta,
) -> None:
    """Test an entity's accumulated history is continued rather than restarted."""
    freezer.move_to(NOW)
    anchor = window()[0] - anchor_age
    async_import_statistics(
        hass, seed_metadata(USAGE), [StatisticData(start=anchor, state=1.0, sum=1000.0)]
    )
    await async_wait_recording_done(hass)

    await setup_and_import(hass, config_entry, freezer)

    rows = (await get_stats(hass, [USAGE], window()[0]))[USAGE]
    assert rows[0]["sum"] == pytest.approx(1000.0 + HOURLY_ENERGY["usage"])


@pytest.mark.parametrize(
    ("period_start", "state"),
    [
        pytest.param("2026-01-15 00:00:00+00:00", PERIOD_TO_DATE, id="same_period"),
        # The period-to-date value belongs to the new period, not to the hour.
        pytest.param("2026-01-15 10:00:00+00:00", 99.0, id="period_reset"),
    ],
)
async def test_import_wins_over_an_existing_row(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_trends: MockTrends,
    period_start: str,
    state: float,
) -> None:
    """Test a row the recorder already compiled for the hour is overwritten.

    The recorder writes its own shifted row for the completed hour at the top of the
    following hour, before any of the four import attempts run.
    """
    freezer.move_to(NOW)
    mock_trends.period_start = dt_util.parse_datetime(period_start)
    hours = window()
    newest = hours[-1]
    last_reset = dt_util.parse_datetime("2026-01-15 00:00:00+00:00")
    async_import_statistics(
        hass,
        seed_metadata(USAGE),
        [
            StatisticData(start=hour, state=99.0, sum=99.0, last_reset=last_reset)
            for hour in hours[-2:]
        ],
    )
    await async_wait_recording_done(hass)

    await setup_and_import(hass, config_entry, freezer)

    rows = (
        await hass.async_add_executor_job(
            statistics_during_period,
            hass,
            hours[0],
            None,
            {USAGE},
            "hour",
            None,
            {"last_reset", "state", "sum"},
        )
    )[USAGE]
    assert rows[-1]["start"] == newest.timestamp()
    assert rows[-1]["sum"] == pytest.approx(HOURLY_ENERGY["usage"] * WINDOW_HOURS)
    assert rows[-1]["state"] == state
    # The recorder's reset time survives the rewrite, as does an older hour's state.
    assert [row["last_reset"] for row in rows[-2:]] == [last_reset.timestamp()] * 2
    assert rows[-2]["state"] == 99.0


async def test_early_reading_of_newest_hour_is_fetched_again(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_trends: MockTrends,
) -> None:
    """Test a reading taken before Sense settled the hour is not kept as final."""
    freezer.move_to(NOW)
    await seed_compiled_hour(hass, window()[-1])
    await setup_platform(hass, config_entry, Platform.SENSOR)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_sense.get_trend_data.call_count == WINDOW_HOURS

    # The hour's final figure, which only the :10 refresh reads.
    mock_trends.energy = HOURLY_ENERGY | {"usage": 2.0}
    await trigger_trend_refresh(hass, freezer)
    await async_wait_recording_done(hass)

    assert mock_sense.get_trend_data.call_count == WINDOW_HOURS + 1
    rows = (await get_stats(hass, [USAGE]))[USAGE]
    assert rows[-1]["sum"] == pytest.approx(
        HOURLY_ENERGY["usage"] * (WINDOW_HOURS - 1) + 2.0
    )


@pytest.mark.parametrize(
    ("compiled", "imported"),
    [
        pytest.param([], 0, id="nothing_compiled"),
        pytest.param([3], 4, id="catching_up"),
    ],
)
async def test_hours_the_recorder_has_not_compiled_are_left_alone(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    compiled: list[int],
    imported: int,
) -> None:
    """Test no row is written ahead of the recorder, whose compile it would abort."""
    freezer.move_to(NOW)
    hours = window()
    async_import_statistics(
        hass,
        seed_metadata(USAGE),
        [
            StatisticData(start=hours[index], state=SEED_VALUE, sum=SEED_VALUE)
            for index in compiled
        ],
    )
    await async_wait_recording_done(hass)

    await setup_platform(hass, config_entry, Platform.SENSOR)
    await trigger_trend_refresh(hass, freezer)
    await async_wait_recording_done(hass)

    rows = (await get_stats(hass, [USAGE])).get(USAGE, [])
    assert [row["start"] for row in rows] == [
        hour.timestamp() for hour in hours[:imported]
    ]


async def test_keeps_the_existing_statistics_unit(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test statistics stored in another energy unit are continued in that unit."""
    freezer.move_to(NOW)
    hours = window()
    metadata = seed_metadata(USAGE, UnitOfEnergy.WATT_HOUR)
    async_import_statistics(
        hass,
        metadata,
        [
            StatisticData(start=hours[0] - timedelta(hours=1), state=1.0, sum=1000.0),
            StatisticData(start=hours[-1], state=1.0, sum=1000.0),
        ],
    )
    await async_wait_recording_done(hass)

    await setup_and_import(hass, config_entry, freezer)

    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        hours[0],
        None,
        {USAGE},
        "hour",
        {EnergyConverter.UNIT_CLASS: UnitOfEnergy.WATT_HOUR},
        {"state", "sum"},
    )
    assert [row["sum"] for row in stats[USAGE]] == pytest.approx(
        [
            1000.0 + HOURLY_ENERGY["usage"] * 1000 * (index + 1)
            for index in range(WINDOW_HOURS)
        ]
    )
    assert stats[USAGE][-1]["state"] == PERIOD_TO_DATE * 1000
    metadata_now = await hass.async_add_executor_job(
        lambda: get_metadata(hass, statistic_ids={USAGE})
    )
    assert metadata_now[USAGE][1]["unit_of_measurement"] == UnitOfEnergy.WATT_HOUR


async def test_window_rewrite_is_idempotent(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the further refreshes of the same hour change nothing."""
    freezer.move_to(NOW)
    await setup_and_import(hass, config_entry, freezer)
    first = await get_stats(hass, [USAGE, PRODUCTION, FROM_GRID, TO_GRID])

    # The next two attempts of the hour, at :25 and :40.
    for _ in range(2):
        await trigger_trend_refresh(hass, freezer)
        await async_wait_recording_done(hass)

    assert await get_stats(hass, [USAGE, PRODUCTION, FROM_GRID, TO_GRID]) == first


async def test_recovers_after_missed_refreshes(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_trends: MockTrends,
) -> None:
    """Test failed attempts of the hour still leave it correct once one succeeds."""
    freezer.move_to(NOW)
    hour_fetch = mock_sense.get_trend_data.side_effect
    mock_sense.get_trend_data.side_effect = SenseAPIException("boom")
    # The attempts at :10 and :25 both fail.
    await setup_and_import(hass, config_entry, freezer)
    await trigger_trend_refresh(hass, freezer)
    await async_wait_recording_done(hass)
    assert await get_sums(hass, USAGE) == [SEED_VALUE]

    # The attempt at :40 rewrites the whole window.
    mock_sense.get_trend_data.side_effect = hour_fetch
    await trigger_trend_refresh(hass, freezer)
    await async_wait_recording_done(hass)

    rows = (await get_stats(hass, [USAGE]))[USAGE]
    assert [row["start"] for row in rows] == [hour.timestamp() for hour in window()]


async def test_does_not_fabricate_across_a_gap(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_trends: MockTrends,
) -> None:
    """Test a hole in the window stops the import instead of closing the gap."""
    freezer.move_to(NOW)
    hours = window()
    mock_trends.missing = {hours[2]}
    await setup_and_import(hass, config_entry, freezer)

    rows = (await get_stats(hass, [USAGE]))[USAGE]
    assert [row["start"] for row in rows] == [
        hour.timestamp() for hour in (*hours[:2], hours[-1])
    ]
    assert rows[-1]["sum"] == SEED_VALUE


async def test_ignores_mismatched_trend_start(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_trends: MockTrends,
) -> None:
    """Test nothing is written when the API answers for a different hour."""
    freezer.move_to(NOW)
    mock_trends.missing = set(window())
    await setup_and_import(hass, config_entry, freezer)

    assert await get_sums(hass, USAGE) == [SEED_VALUE]


async def test_without_solar_the_solar_streams_stay_flat(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_trends: MockTrends,
) -> None:
    """Test a monitor without solar reports no energy on the solar streams."""
    freezer.move_to(NOW)
    mock_trends.energy = dict.fromkeys(HOURLY_ENERGY, 0.0) | {"usage": 1.5}
    await setup_and_import(hass, config_entry, freezer)

    stats = await get_stats(hass, [USAGE, PRODUCTION, FROM_GRID, TO_GRID])
    assert [row["sum"] for row in stats[USAGE]] != [0.0] * WINDOW_HOURS
    for entity_id in (PRODUCTION, FROM_GRID, TO_GRID):
        assert [row["sum"] for row in stats[entity_id]] == [0.0] * WINDOW_HOURS


@pytest.mark.parametrize(
    "now",
    [
        pytest.param("2025-03-09 08:01:00+00:00", id="spring_forward"),
        pytest.param("2025-11-02 06:01:00+00:00", id="fall_back"),
    ],
)
async def test_dst_transitions_produce_contiguous_hours(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    now: str,
) -> None:
    """Test the window spans a DST changeover without a duplicate or missing bucket."""
    await hass.config.async_set_time_zone("America/New_York")
    freezer.move_to(now)
    await setup_and_import(hass, config_entry, freezer)

    rows = (await get_stats(hass, [USAGE], dt_util.utc_from_timestamp(0)))[USAGE]
    starts = [row["start"] for row in rows]
    assert starts == [hour.timestamp() for hour in window(now)]
    assert len(set(starts)) == WINDOW_HOURS


async def test_skips_disabled_entities(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a disabled sensor gets no statistics, which would have no state to match."""
    freezer.move_to(NOW)
    config_entry.add_to_hass(hass)
    disabled = entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        f"{MONITOR_ID}-daily-to_grid",
        config_entry=config_entry,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    await setup_and_import(hass, config_entry, freezer)

    assert len(await get_sums(hass, USAGE)) == WINDOW_HOURS
    assert await get_sums(hass, disabled.entity_id) == [SEED_VALUE]


@pytest.mark.parametrize(
    "recorder_config", [{CONF_EXCLUDE: {CONF_ENTITIES: [TO_GRID]}}]
)
async def test_skips_entities_excluded_from_recorder(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a sensor the user excluded from the recorder gets no statistics."""
    freezer.move_to(NOW)
    await setup_and_import(hass, config_entry, freezer)

    assert len(await get_sums(hass, USAGE)) == WINDOW_HOURS
    assert await get_sums(hass, TO_GRID) == [SEED_VALUE]


async def test_entities_keep_their_state_class(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test taking over the statistics leaves the entities and their repairs alone."""
    freezer.move_to(NOW)
    await setup_and_import(hass, config_entry, freezer)

    state = hass.states.get(USAGE)
    assert state.attributes[ATTR_STATE_CLASS] is SensorStateClass.TOTAL
    assert not [
        issue
        for issue in issue_registry.issues.values()
        if issue.translation_key == "state_class_removed"
    ]


async def test_refreshes_are_phase_locked(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test refreshes run after the recorder's hourly compile, never alongside it."""
    freezer.move_to("2026-01-15 10:05:00+00:00")
    await setup_platform(hass, config_entry, Platform.SENSOR)
    await hass.async_block_till_done(wait_background_tasks=True)
    # Flush the refresh the debouncer still has scheduled from setup.
    await trigger_trend_refresh(hass, freezer)

    for minute in TREND_UPDATE_MINUTES[1:]:
        calls = mock_sense.update_trend_data.call_count
        await trigger_trend_refresh(hass, freezer)
        assert dt_util.utcnow().minute == minute
        assert mock_sense.update_trend_data.call_count == calls + 1

    # Nothing refreshes at the top of the hour, where the recorder compiles, nor at
    # the provisional import, which reads nothing from Sense.
    calls = mock_sense.update_trend_data.call_count
    for now in ("2026-01-15 11:00:00+00:00", "2026-01-15 11:01:00+00:00"):
        freezer.move_to(now)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert mock_sense.update_trend_data.call_count == calls


async def test_statistics_failure_does_not_break_the_sensors(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the trend sensors keep updating when the hourly fetch fails."""
    freezer.move_to(NOW)
    mock_sense.get_trend_data.side_effect = SenseAPIException("boom")
    await setup_and_import(hass, config_entry, freezer)

    assert await get_sums(hass, USAGE) == [SEED_VALUE]
    assert hass.states.get(USAGE).state == str(PERIOD_TO_DATE)


async def fire_provisional_import(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, now: str
) -> None:
    """Move the clock to the provisional import at now and run it."""
    freezer.move_to(now)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    await async_wait_recording_done(hass)


async def test_provisional_import_replaces_recorder_row(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_trends: MockTrends,
) -> None:
    """Test the recorder's row for the newest hour is replaced before the first refresh.

    The recorder compiles that row from its own running sum, which does not follow
    the imported one, so left alone it shows a wrong bar until the :10 refresh.
    """
    freezer.move_to("2026-01-15 09:50:00+00:00")
    # The refresh at :55 also reads the in-progress 09:00 hour.
    await setup_and_import(hass, config_entry, freezer)
    newest = dt_util.parse_datetime("2026-01-15 09:00:00+00:00")
    freezer.move_to("2026-01-15 10:00:30+00:00")
    async_import_statistics(
        hass,
        seed_metadata(USAGE),
        [StatisticData(start=newest, state=99.0, sum=99.0)],
    )
    await async_wait_recording_done(hass)
    # The hour's final figure, which only the :10 refresh reads.
    mock_trends.energy = HOURLY_ENERGY | {"usage": 2.0}
    fetches = mock_sense.get_trend_data.call_count

    await fire_provisional_import(hass, freezer, "2026-01-15 10:01:00+00:00")

    assert mock_sense.get_trend_data.call_count == fetches
    rows = (await get_stats(hass, [USAGE]))[USAGE]
    assert rows[-1]["start"] == newest.timestamp()
    assert rows[-1]["sum"] == pytest.approx(HOURLY_ENERGY["usage"] * (WINDOW_HOURS + 1))

    await trigger_trend_refresh(hass, freezer)
    await async_wait_recording_done(hass)

    rows = (await get_stats(hass, [USAGE]))[USAGE]
    assert rows[-1]["start"] == newest.timestamp()
    assert rows[-1]["sum"] == pytest.approx(HOURLY_ENERGY["usage"] * WINDOW_HOURS + 2.0)


async def test_provisional_import_needs_an_in_progress_reading(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_trends: MockTrends,
) -> None:
    """Test nothing is written for the newest hour when the read at :55 failed."""
    freezer.move_to("2026-01-15 09:50:00+00:00")
    mock_trends.missing = {dt_util.parse_datetime("2026-01-15 09:00:00+00:00")}
    await setup_and_import(hass, config_entry, freezer)
    before = await get_stats(hass, [USAGE])

    await fire_provisional_import(hass, freezer, "2026-01-15 10:01:00+00:00")

    assert await get_stats(hass, [USAGE]) == before
