"""Tests for Google Health sensor platform."""

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from google_health_api.const import HealthApiScope
from google_health_api.model import (
    SLEEP,
    ActiveMinutesRollupByActivityLevel,
    ActiveMinutesRollupValue,
    ActiveZoneMinutesRollupValue,
    AltitudeRollupValue,
    ListPairedDevicesResult,
    NutrientQuantityRollup,
    NutritionLogRollupValue,
    SedentaryPeriodRollupValue,
    StageSummary,
    WeightQuantityRollup,
    _ListPairedDevicesModel,
)
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.google_health.const import DOMAIN
from homeassistant.components.google_health.coordinator import DEVICE_POLLING_INTERVAL
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)

from .conftest import _list_fixture, _rollup_fixture, paired_devices_fixture


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_google_health_client"
)
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test all sensor entities."""
    with patch("homeassistant.components.google_health._PLATFORMS", [Platform.SENSOR]):
        assert await integration_setup()

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.usefixtures("mock_google_health_client")
async def test_sensor_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test default enabled and disabled states for all sensor entities."""
    with patch("homeassistant.components.google_health._PLATFORMS", [Platform.SENSOR]):
        assert await integration_setup()

    entries = er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    expected_disabled = {
        "sensor.google_health_sedentary_time": er.RegistryEntryDisabler.INTEGRATION,
        "sensor.google_health_fat_burn_active_zone_minutes": (
            er.RegistryEntryDisabler.INTEGRATION
        ),
        "sensor.google_health_cardio_active_zone_minutes": (
            er.RegistryEntryDisabler.INTEGRATION
        ),
        "sensor.google_health_peak_active_zone_minutes": (
            er.RegistryEntryDisabler.INTEGRATION
        ),
        "sensor.google_health_dietary_fiber": er.RegistryEntryDisabler.INTEGRATION,
        "sensor.google_health_sugar": er.RegistryEntryDisabler.INTEGRATION,
        "sensor.google_health_sodium": er.RegistryEntryDisabler.INTEGRATION,
        "sensor.google_health_calories_from_fat": er.RegistryEntryDisabler.INTEGRATION,
    }
    assert {
        entry.entity_id: entry.disabled_by
        for entry in entries
        if entry.disabled_by is not None
    } == expected_disabled
    assert {
        entry.entity_id for entry in entries if hass.states.get(entry.entity_id) is None
    } == set(expected_disabled)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_empty_rollup(
    hass: HomeAssistant,
    mock_google_health_client: AsyncMock,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test rollup sensors when the rollup endpoints return no data."""
    mock_google_health_client.steps.today.return_value = None
    mock_google_health_client.distance.today.return_value = None
    mock_google_health_client.active_energy_burned.today.return_value = None
    mock_google_health_client.total_calories.today.return_value = None
    mock_google_health_client.floors.today.return_value = None
    mock_google_health_client.altitude.today.return_value = None
    mock_google_health_client.active_minutes.today.return_value = None
    mock_google_health_client.active_zone_minutes.today.return_value = None
    mock_google_health_client.sedentary_period.today.return_value = None
    mock_google_health_client.hydration_log.today.return_value = None
    mock_google_health_client.nutrition_log.today.return_value = None

    assert await integration_setup()

    expected_states = {
        "sensor.google_health_steps": "0",
        "sensor.google_health_distance": "0.0",
        "sensor.google_health_active_calories": "0.0",
        "sensor.google_health_total_calories": "0.0",
        "sensor.google_health_floors": "0",
        "sensor.google_health_elevation": "0.0",
        "sensor.google_health_light_activity": "0",
        "sensor.google_health_moderate_activity": "0",
        "sensor.google_health_vigorous_activity": "0",
        "sensor.google_health_active_zone_minutes": "0",
        "sensor.google_health_sedentary_time": "0.0",
        "sensor.google_health_fat_burn_active_zone_minutes": "0",
        "sensor.google_health_cardio_active_zone_minutes": "0",
        "sensor.google_health_peak_active_zone_minutes": "0",
        "sensor.google_health_water_intake": "0.0",
        "sensor.google_health_calories_consumed": "0.0",
        "sensor.google_health_total_fat": "0.0",
        "sensor.google_health_total_carbohydrates": "0.0",
        "sensor.google_health_protein": "0.0",
        "sensor.google_health_dietary_fiber": "0.0",
        "sensor.google_health_sugar": "0.0",
        "sensor.google_health_sodium": "0.0",
        "sensor.google_health_calories_from_fat": "0.0",
    }
    assert {
        entity_id: getattr(hass.states.get(entity_id), "state", None)
        for entity_id in expected_states
    } == expected_states


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_activity_partial_rollup(
    hass: HomeAssistant,
    mock_google_health_client: AsyncMock,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test activity sensors when rollups contain only a subset of fields and levels."""
    altitude_rollup = _rollup_fixture("altitude.json", AltitudeRollupValue, "altitude")
    assert altitude_rollup is not None
    altitude_rollup.data = AltitudeRollupValue()
    mock_google_health_client.altitude.today.return_value = altitude_rollup

    active_minutes_rollup = _rollup_fixture(
        "active_minutes.json", ActiveMinutesRollupValue, "activeMinutes"
    )
    assert active_minutes_rollup is not None
    active_minutes_rollup.data = ActiveMinutesRollupValue(
        active_minutes_rollup_by_activity_level=[
            ActiveMinutesRollupByActivityLevel(
                activity_level="MODERATE",
                active_minutes_sum=20,
            )
        ]
    )
    mock_google_health_client.active_minutes.today.return_value = active_minutes_rollup

    azm_rollup = _rollup_fixture(
        "active_zone_minutes.json",
        ActiveZoneMinutesRollupValue,
        "activeZoneMinutes",
    )
    assert azm_rollup is not None
    azm_rollup.data = ActiveZoneMinutesRollupValue(sum_in_fat_burn_heart_zone=12)
    mock_google_health_client.active_zone_minutes.today.return_value = azm_rollup

    sedentary_rollup = _rollup_fixture(
        "sedentary_period.json",
        SedentaryPeriodRollupValue,
        "sedentaryPeriod",
    )
    assert sedentary_rollup is not None
    sedentary_rollup.data = SedentaryPeriodRollupValue()
    mock_google_health_client.sedentary_period.today.return_value = sedentary_rollup

    assert await integration_setup()

    expected_states = {
        "sensor.google_health_elevation": "0.0",
        "sensor.google_health_light_activity": "0",
        "sensor.google_health_moderate_activity": "20",
        "sensor.google_health_vigorous_activity": "0",
        "sensor.google_health_active_zone_minutes": "12",
        "sensor.google_health_sedentary_time": "0.0",
        "sensor.google_health_fat_burn_active_zone_minutes": "12",
        "sensor.google_health_cardio_active_zone_minutes": "0",
        "sensor.google_health_peak_active_zone_minutes": "0",
    }
    assert {
        entity_id: getattr(hass.states.get(entity_id), "state", None)
        for entity_id in expected_states
    } == expected_states


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_nutrition_partial_rollup(
    hass: HomeAssistant,
    mock_google_health_client: AsyncMock,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test nutrition sensors when rollup contains only a subset of fields and nutrients."""
    nutrition_rollup = _rollup_fixture(
        "nutrition.json", NutritionLogRollupValue, "nutritionLog"
    )
    assert nutrition_rollup is not None
    nutrition_rollup.data = NutritionLogRollupValue(
        nutrients=[
            NutrientQuantityRollup(
                nutrient="PROTEIN",
                quantity=WeightQuantityRollup(grams_sum=30.5),
            )
        ]
    )
    mock_google_health_client.nutrition_log.today.return_value = nutrition_rollup

    assert await integration_setup()

    expected_states = {
        "sensor.google_health_calories_consumed": "0.0",
        "sensor.google_health_total_fat": "0.0",
        "sensor.google_health_total_carbohydrates": "0.0",
        "sensor.google_health_protein": "30.5",
        "sensor.google_health_dietary_fiber": "0.0",
        "sensor.google_health_sugar": "0.0",
        "sensor.google_health_sodium": "0.0",
        "sensor.google_health_calories_from_fat": "0.0",
    }
    assert {
        entity_id: getattr(hass.states.get(entity_id), "state", None)
        for entity_id in expected_states
    } == expected_states


async def test_sensor_empty_sleep(
    hass: HomeAssistant,
    mock_google_health_client: AsyncMock,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test sleep sensors when the sleep endpoint returns no data."""
    mock_google_health_client.sleep.list.return_value = MagicMock(data_points=[])

    assert await integration_setup()

    for entity_id in (
        "sensor.google_health_time_asleep",
        "sensor.google_health_sleep_start_time",
        "sensor.google_health_sleep_end_time",
        "sensor.google_health_rem_sleep",
        "sensor.google_health_deep_sleep",
        "sensor.google_health_light_sleep",
    ):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_UNKNOWN


async def test_sensor_in_progress_sleep(
    hass: HomeAssistant,
    mock_google_health_client: AsyncMock,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test sleep sensors return latest completed session when an active session is in progress."""
    mock_google_health_client.sleep.list.return_value = _list_fixture(
        "sleep_in_progress.json", SLEEP
    )

    assert await integration_setup()

    for entity_id, expected in (
        ("sensor.google_health_time_asleep", "7.0"),
        ("sensor.google_health_time_awake", "1.0"),
        ("sensor.google_health_time_in_bed", "8.0"),
        ("sensor.google_health_time_to_fall_asleep", "15"),
        ("sensor.google_health_time_after_waking_up", "10"),
        ("sensor.google_health_sleep_start_time", "2026-08-15T22:00:00+00:00"),
        ("sensor.google_health_sleep_end_time", "2026-08-16T06:00:00+00:00"),
        ("sensor.google_health_rem_sleep", "1.5"),
        ("sensor.google_health_deep_sleep", "1.5"),
        ("sensor.google_health_light_sleep", "4.0"),
    ):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == expected


@pytest.mark.parametrize(
    ("stages_summary", "expected_states"),
    [
        pytest.param(
            None,
            {
                "sensor.google_health_rem_sleep": STATE_UNKNOWN,
                "sensor.google_health_deep_sleep": STATE_UNKNOWN,
                "sensor.google_health_light_sleep": STATE_UNKNOWN,
            },
            id="no_stages_summary",
        ),
        pytest.param(
            [StageSummary(type="LIGHT", minutes=240, count=24)],
            {
                "sensor.google_health_rem_sleep": STATE_UNKNOWN,
                "sensor.google_health_deep_sleep": STATE_UNKNOWN,
                "sensor.google_health_light_sleep": "4.0",
            },
            id="partial_stages_summary",
        ),
    ],
)
async def test_sensor_sleep_missing_stages(
    hass: HomeAssistant,
    mock_google_health_client: AsyncMock,
    integration_setup: Callable[[], Awaitable[bool]],
    stages_summary: list[StageSummary] | None,
    expected_states: dict[str, str],
) -> None:
    """Test sleep stage sensors when stages summary is missing or partial."""
    sleep_result = _list_fixture("sleep.json", SLEEP)
    assert sleep_result.data_points[0].data.summary is not None
    sleep_result.data_points[0].data.summary.stages_summary = stages_summary
    mock_google_health_client.sleep.list.return_value = sleep_result

    assert await integration_setup()

    for entity_id, expected_state in expected_states.items():
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == expected_state


async def test_sensor_only_in_progress_sleep(
    hass: HomeAssistant,
    mock_google_health_client: AsyncMock,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test sleep sensors when only an in-progress session with no summary exists."""
    full_fixture = _list_fixture("sleep_in_progress.json", SLEEP)
    mock_google_health_client.sleep.list.return_value = MagicMock(
        data_points=full_fixture.data_points[:1]
    )

    assert await integration_setup()

    time_asleep_state = hass.states.get("sensor.google_health_time_asleep")
    assert time_asleep_state is not None
    assert time_asleep_state.state == "unknown"


@pytest.mark.parametrize(
    ("unit_system", "expected_sensors"),
    [
        pytest.param(
            METRIC_SYSTEM,
            {
                "sensor.google_health_weight": (pytest.approx(80.0), "kg"),
                "sensor.google_health_distance": (pytest.approx(5.0), "km"),
                "sensor.google_health_elevation": (pytest.approx(150.0), "m"),
                "sensor.google_health_water_intake": (pytest.approx(2.5), "L"),
                "sensor.google_health_total_fat": (pytest.approx(65.0), "g"),
            },
            id="metric",
        ),
        pytest.param(
            US_CUSTOMARY_SYSTEM,
            {
                "sensor.google_health_weight": (pytest.approx(176.37, abs=1e-2), "lb"),
                "sensor.google_health_distance": (
                    pytest.approx(3.11, abs=1e-2),
                    "mi",
                ),
                "sensor.google_health_elevation": (
                    pytest.approx(492.13, abs=1e-2),
                    "ft",
                ),
                "sensor.google_health_water_intake": (
                    pytest.approx(84.54, abs=1e-1),
                    "fl. oz.",
                ),
                "sensor.google_health_total_fat": (pytest.approx(65.0), "g"),
            },
            id="us_customary",
        ),
    ],
)
@pytest.mark.usefixtures("mock_google_health_client")
async def test_sensor_unit_conversions(
    hass: HomeAssistant,
    integration_setup: Callable[[], Awaitable[bool]],
    unit_system: UnitSystem,
    expected_sensors: dict[str, tuple[Any, str]],
) -> None:
    """Test sensors dynamically convert states and units under different unit systems."""
    hass.config.units = unit_system

    assert await integration_setup()

    for entity_id, (expected_state, expected_unit) in expected_sensors.items():
        state = hass.states.get(entity_id)
        assert state is not None
        assert float(state.state) == expected_state
        assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == expected_unit


@pytest.mark.parametrize(
    "scopes",
    [[HealthApiScope.PROFILE_READ, HealthApiScope.SETTINGS_READ]],
    indirect=True,
)
@pytest.mark.usefixtures("mock_google_health_client")
async def test_device_sensor_via_device_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test a paired device is linked to the account device via via_device_id.

    Only the profile and settings scopes are granted so the account device
    can only come from the up-front registration, not from account-level
    sensors that scopes outside of this test would also create.
    """
    with patch("homeassistant.components.google_health._PLATFORMS", [Platform.SENSOR]):
        assert await integration_setup()

    account_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, config_entry.entry_id), config_entry.entry_id
    )
    assert account_device is not None

    paired_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "watch_123"), config_entry.entry_id
    )
    assert paired_device is not None
    assert paired_device.via_device_id == account_device.id


async def test_stale_device_removed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_google_health_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test stale devices are removed when no longer returned by API."""
    assert await integration_setup()

    battery_state = hass.states.get("sensor.fitbit_charge_6_battery")
    assert battery_state is not None
    assert battery_state.state == "85"

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "watch_123"), config_entry.entry_id
    )
    assert device is not None

    mock_google_health_client.paired_devices.list.return_value = (
        ListPairedDevicesResult(_ListPairedDevicesModel([]))
    )

    freezer.tick(DEVICE_POLLING_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.fitbit_charge_6_battery") is None

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "watch_123"), config_entry.entry_id
    )
    assert device is None


@pytest.mark.usefixtures("mock_google_health_client")
async def test_stale_device_removed_on_setup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test stale device present in registry before setup is removed during setup."""
    config_entry.add_to_hass(hass)
    stale_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "old_stale_watch")},
        name="Old Stale Watch",
    )
    assert device_registry.async_get(stale_device.id) is not None

    assert await integration_setup()

    assert device_registry.async_get(stale_device.id) is None


async def test_auto_add_new_device(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_google_health_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test new paired devices returned on coordinator update are automatically added."""
    mock_google_health_client.paired_devices.list.return_value = (
        ListPairedDevicesResult(_ListPairedDevicesModel([]))
    )

    assert await integration_setup()

    assert hass.states.get("sensor.fitbit_charge_6_battery") is None
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "watch_123"), config_entry.entry_id
        )
        is None
    )

    mock_google_health_client.paired_devices.list.return_value = paired_devices_fixture(
        "paired_devices.json"
    )

    freezer.tick(DEVICE_POLLING_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    battery_state = hass.states.get("sensor.fitbit_charge_6_battery")
    assert battery_state is not None
    assert battery_state.state == "85"

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "watch_123"), config_entry.entry_id
    )
    assert device is not None
