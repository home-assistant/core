"""Test Withings weight statistics backfill."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from functools import partial
from unittest.mock import AsyncMock

from aiowithings import Measurement, MeasurementAttribution, MeasurementType
from aiowithings.models import MeasurementGroup, MeasurementGroupCategory
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.recorder.common import async_wait_recording_done

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.models import (
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_import_statistics,
    get_metadata,
    statistics_during_period,
)
from homeassistant.components.withings.const import DOMAIN
from homeassistant.const import ATTR_CONFIG_ENTRY_ID, UnitOfMass
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import load_measurements_fixture, setup_integration

ENTITY_ID = "sensor.henk_weight"
RENAMED_ENTITY_ID = "sensor.renamed_weight"
ACTION = "backfill_weight_statistics"
START = datetime(2020, 1, 1, 10, tzinfo=UTC)

pytestmark = pytest.mark.freeze_time("2023-10-21 12:30:00+00:00")


@pytest.fixture
def hass(recorder_db_url: str, hass: HomeAssistant) -> HomeAssistant:
    """Prepare the database before the credentials fixture creates Home Assistant."""
    return hass


@pytest.mark.parametrize(
    ("unit", "expected_mean"),
    [(UnitOfMass.KILOGRAMS, 71), (UnitOfMass.POUNDS, 156.52820615126308)],
)
async def test_backfill_preserves_statistics(
    hass: HomeAssistant,
    recorder_mock: Recorder,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    unit: str,
    expected_mean: float,
) -> None:
    """Import missing hours once using the current entity ID and statistics unit."""
    await setup_integration(hass, polling_config_entry, False)
    entity_registry.async_update_entity(ENTITY_ID, new_entity_id=RENAMED_ENTITY_ID)
    await hass.async_block_till_done()
    state_before = hass.states.get(RENAMED_ENTITY_ID)
    assert state_before is not None

    metadata = StatisticMetaData(
        statistic_id=RENAMED_ENTITY_ID,
        source="recorder",
        name=None,
        mean_type=StatisticMeanType.ARITHMETIC,
        has_sum=False,
        unit_class="mass",
        unit_of_measurement=unit,
    )
    existing_hour = START + timedelta(days=1)
    async_import_statistics(
        hass,
        metadata,
        [{"start": existing_hour, "mean": 80, "min": 79, "max": 81}],
    )
    await async_wait_recording_done(hass)
    original_metadata = await recorder_mock.async_add_executor_job(
        partial(get_metadata, hass, statistic_ids={RENAMED_ENTITY_ID})
    )

    group = load_measurements_fixture()[0]
    withings.get_measurement_in_period.return_value = [
        replace(
            group,
            taken_at=START + timedelta(minutes=15),
            measurements=[Measurement(MeasurementType.WEIGHT, 70)],
        ),
        replace(
            group,
            group_id=2,
            taken_at=datetime(2020, 1, 1, 11, 45, tzinfo=timezone(timedelta(hours=1))),
            measurements=[Measurement(MeasurementType.WEIGHT, 72)],
        ),
        replace(group, group_id=3, taken_at=existing_hour),
        replace(
            group,
            group_id=4,
            taken_at=START - timedelta(hours=1),
            attribution=MeasurementAttribution.DEVICE_ENTRY_FOR_USER_AMBIGUOUS,
        ),
        replace(
            group,
            group_id=5,
            taken_at=START - timedelta(hours=2),
            category=MeasurementGroupCategory.USER_OBJECTIVES,
        ),
        replace(group, group_id=6, taken_at=datetime(2023, 10, 21, 11, tzinfo=UTC)),
        replace(group, group_id=7, taken_at=datetime(2023, 10, 21, 12, tzinfo=UTC)),
    ]
    withings.get_measurement_in_period.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        ACTION,
        {ATTR_CONFIG_ENTRY_ID: polling_config_entry.entry_id},
        blocking=True,
    )
    await async_wait_recording_done(hass)
    withings.get_measurement_in_period.assert_awaited_once_with(
        dt_util.utc_from_timestamp(0),
        datetime(2023, 10, 21, 11, tzinfo=UTC),
        [MeasurementType.WEIGHT],
    )
    before_repeat = await recorder_mock.async_add_executor_job(
        statistics_during_period,
        hass,
        START - timedelta(days=1),
        None,
        {RENAMED_ENTITY_ID},
        "hour",
        {"mass": unit},
        {"mean", "min", "max"},
    )
    rows = before_repeat[RENAMED_ENTITY_ID]
    assert [row["start"] for row in rows] == [
        START.timestamp(),
        existing_hour.timestamp(),
    ]
    assert rows[0]["mean"] == pytest.approx(expected_mean)
    assert rows[0]["min"] == pytest.approx(expected_mean * 70 / 71)
    assert rows[0]["max"] == pytest.approx(expected_mean * 72 / 71)
    assert (rows[1]["mean"], rows[1]["min"], rows[1]["max"]) == (80, 79, 81)

    await hass.services.async_call(
        DOMAIN,
        ACTION,
        {ATTR_CONFIG_ENTRY_ID: polling_config_entry.entry_id},
        blocking=True,
    )
    await async_wait_recording_done(hass)
    assert (
        await recorder_mock.async_add_executor_job(
            statistics_during_period,
            hass,
            START - timedelta(days=1),
            None,
            {RENAMED_ENTITY_ID},
            "hour",
            {"mass": unit},
            {"mean", "min", "max"},
        )
        == before_repeat
    )
    stored_metadata = await recorder_mock.async_add_executor_job(
        partial(get_metadata, hass, statistic_ids={RENAMED_ENTITY_ID})
    )
    assert stored_metadata == original_metadata
    assert hass.states.get(RENAMED_ENTITY_ID) == state_before
    assert hass.states.get(ENTITY_ID) is None


async def test_backfill_without_existing_statistics(
    hass: HomeAssistant,
    recorder_mock: Recorder,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Create native weight statistics without creating another sensor."""
    await setup_integration(hass, polling_config_entry, False)
    withings.get_measurement_in_period.return_value = [
        replace(load_measurements_fixture()[0], taken_at=START)
    ]
    await hass.services.async_call(
        DOMAIN,
        ACTION,
        {ATTR_CONFIG_ENTRY_ID: polling_config_entry.entry_id},
        blocking=True,
    )
    await async_wait_recording_done(hass)
    rows = await recorder_mock.async_add_executor_job(
        statistics_during_period, hass, START, None, {ENTITY_ID}, "hour", None, {"mean"}
    )
    assert len(rows[ENTITY_ID]) == 1
    assert rows[ENTITY_ID][0]["mean"] == 70
    metadata = await recorder_mock.async_add_executor_job(
        partial(get_metadata, hass, statistic_ids={ENTITY_ID})
    )
    assert metadata[ENTITY_ID][1]["unit_of_measurement"] == UnitOfMass.KILOGRAMS
    assert metadata[ENTITY_ID][1]["source"] == "recorder"


async def test_backfill_api_failure(
    hass: HomeAssistant,
    recorder_mock: Recorder,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """A failed history request does not import partial statistics."""
    await setup_integration(hass, polling_config_entry, False)
    withings.get_measurement_in_period.side_effect = TimeoutError
    with pytest.raises(HomeAssistantError, match="Could not retrieve weight history"):
        await hass.services.async_call(
            DOMAIN,
            ACTION,
            {ATTR_CONFIG_ENTRY_ID: polling_config_entry.entry_id},
            blocking=True,
        )
    assert (
        await recorder_mock.async_add_executor_job(
            partial(get_metadata, hass, statistic_ids={ENTITY_ID})
        )
        == {}
    )


async def test_backfill_sensor_renamed_during_fetch(
    hass: HomeAssistant,
    recorder_mock: Recorder,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Do not import under the old ID when the sensor is renamed during a fetch."""
    await setup_integration(hass, polling_config_entry, False)

    async def rename_during_fetch(*args: object) -> list[MeasurementGroup]:
        entity_registry.async_update_entity(ENTITY_ID, new_entity_id=RENAMED_ENTITY_ID)
        return [replace(load_measurements_fixture()[0], taken_at=START)]

    withings.get_measurement_in_period.side_effect = rename_during_fetch
    with pytest.raises(ServiceValidationError, match="weight sensor changed"):
        await hass.services.async_call(
            DOMAIN,
            ACTION,
            {ATTR_CONFIG_ENTRY_ID: polling_config_entry.entry_id},
            blocking=True,
        )
    await async_wait_recording_done(hass)
    assert (
        await recorder_mock.async_add_executor_job(
            partial(get_metadata, hass, statistic_ids={ENTITY_ID, RENAMED_ENTITY_ID})
        )
        == {}
    )


async def test_backfill_requires_recorder(
    hass: HomeAssistant,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Explain the missing Recorder prerequisite before fetching history."""
    await setup_integration(hass, polling_config_entry, False)
    withings.get_measurement_in_period.reset_mock()
    with pytest.raises(
        ServiceValidationError, match="Recorder integration must be enabled"
    ):
        await hass.services.async_call(
            DOMAIN,
            ACTION,
            {ATTR_CONFIG_ENTRY_ID: polling_config_entry.entry_id},
            blocking=True,
        )
    withings.get_measurement_in_period.assert_not_awaited()
