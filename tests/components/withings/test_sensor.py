"""Tests for the Withings component."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from aiowithings import Goals, NotificationCategory
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.withings import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import (
    call_webhook,
    load_activity_fixture,
    load_device_fixture,
    load_goals_fixture,
    load_measurements_fixture,
    load_sleep_fixture,
    load_workout_fixture,
    prepare_webhook_setup,
    setup_integration,
)
from .conftest import USER_ID, WEBHOOK_ID


@pytest.mark.freeze_time("2023-10-21 12:00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.withings.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, polling_config_entry)

    await snapshot_platform(
        hass, entity_registry, snapshot, polling_config_entry.entry_id
    )


async def test_update_failed(
    hass: HomeAssistant,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test all entities."""
    await setup_integration(hass, polling_config_entry, False)

    withings.get_measurement_since.side_effect = Exception
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.henk_weight")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_update_updates_incrementally(
    hass: HomeAssistant,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test fetching new data updates since the last valid update."""
    await setup_integration(hass, polling_config_entry, False)

    async def _skip_10_minutes() -> None:
        freezer.tick(timedelta(minutes=10))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert withings.get_measurement_since.call_args_list == []
    await _skip_10_minutes()
    assert (
        str(withings.get_measurement_since.call_args_list[0].args[0])
        == "2019-08-01 12:00:00+00:00"
    )

    withings.get_measurement_since.return_value = load_measurements_fixture(
        "withings/measurements_1.json"
    )

    await _skip_10_minutes()
    assert (
        str(withings.get_measurement_since.call_args_list[1].args[0])
        == "2019-08-01 12:00:00+00:00"
    )

    await _skip_10_minutes()
    assert (
        str(withings.get_measurement_since.call_args_list[2].args[0])
        == "2021-04-16 20:30:55+00:00"
    )

    state = hass.states.get("sensor.henk_weight")
    assert state is not None
    assert state.state == "71"
    assert len(withings.get_measurement_in_period.call_args_list) == 1


async def test_workout_sensor_keeps_latest_workout_after_webhook_updates(
    hass: HomeAssistant,
    withings: AsyncMock,
    webhook_config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test webhook updates accept newer/equal workouts and ignore older ones."""
    initial = replace(load_workout_fixture()[0], distance=100)
    newer = replace(
        initial,
        end_date=initial.end_date + timedelta(hours=1),
        distance=200,
    )
    older = replace(
        initial,
        end_date=initial.end_date - timedelta(minutes=1),
        distance=50,
    )
    equal = replace(newer, distance=250)
    withings.get_workouts_in_period.return_value = [initial]
    withings.get_workouts_since.side_effect = [[older, newer], [older], [equal]]

    await setup_integration(hass, webhook_config_entry)
    await prepare_webhook_setup(hass, freezer)
    client = await hass_client_no_auth()
    sensor = "sensor.henk_distance_travelled_last_workout"
    calendar = "calendar.henk_workouts"

    async def _webhook_update(expected_distance: str) -> None:
        response = await call_webhook(
            hass,
            WEBHOOK_ID,
            {"userid": USER_ID, "appli": NotificationCategory.ACTIVITY},
            client,
        )
        assert response.message_code == 0
        state = hass.states.get(sensor)
        assert state is not None
        assert state.state == expected_distance
        assert hass.states.get(calendar) is not None
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    state = hass.states.get(sensor)
    assert state is not None
    assert state.state == "100"
    assert hass.states.get(calendar) is not None

    await _webhook_update("200")
    await _webhook_update("200")
    await _webhook_update("250")

    assert [call.args[0] for call in withings.get_workouts_since.call_args_list] == [
        initial.end_date,
        newer.end_date,
        newer.end_date,
    ]


async def test_update_new_measurement_creates_new_sensor(
    hass: HomeAssistant,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test fetching a new measurement will add a new sensor."""
    withings.get_measurement_in_period.return_value = load_measurements_fixture(
        "withings/measurements_1.json"
    )
    await setup_integration(hass, polling_config_entry, False)

    assert hass.states.get("sensor.henk_fat_mass") is None

    withings.get_measurement_in_period.return_value = load_measurements_fixture()

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.henk_fat_mass")


async def test_update_new_goals_creates_new_sensor(
    hass: HomeAssistant,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test fetching new goals will add a new sensor."""

    withings.get_goals.return_value = load_goals_fixture("withings/goals_1.json")

    await setup_integration(hass, polling_config_entry, False)

    assert hass.states.get("sensor.henk_step_goal") is None
    assert hass.states.get("sensor.henk_weight_goal")

    withings.get_goals.return_value = load_goals_fixture()

    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.henk_step_goal")


async def test_activity_sensors_unknown_next_day(
    hass: HomeAssistant,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test activity sensors will return unknown the next day."""
    freezer.move_to("2023-10-21 12:00:00")
    await setup_integration(hass, polling_config_entry, False)

    assert hass.states.get("sensor.henk_steps_today")

    withings.get_activities_since.return_value = []

    freezer.tick(timedelta(days=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.henk_steps_today").state == STATE_UNKNOWN


async def test_activity_sensors_same_result_same_day(
    hass: HomeAssistant,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test activity sensors will return the same result if old data is updated."""
    freezer.move_to("2023-10-21 12:00:00")
    await setup_integration(hass, polling_config_entry, False)

    assert hass.states.get("sensor.henk_steps_today").state == "1155"

    withings.get_activities_since.return_value = []

    freezer.tick(timedelta(hours=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.henk_steps_today").state == "1155"


async def test_activity_sensors_created_when_existed(
    hass: HomeAssistant,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test activity sensors will be added if they existed before."""
    freezer.move_to("2023-10-21 12:00:00")
    await setup_integration(hass, polling_config_entry, False)

    assert hass.states.get("sensor.henk_steps_today")
    assert hass.states.get("sensor.henk_steps_today").state != STATE_UNKNOWN

    withings.get_activities_in_period.return_value = []

    await hass.config_entries.async_reload(polling_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.henk_steps_today").state == STATE_UNKNOWN


async def test_activity_sensors_created_when_receive_activity_data(
    hass: HomeAssistant,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test activity sensors will be added if we receive activity data."""
    freezer.move_to("2023-10-21 12:00:00")
    withings.get_activities_in_period.return_value = []
    await setup_integration(hass, polling_config_entry, False)

    assert hass.states.get("sensor.henk_steps_today") is None

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.henk_steps_today") is None

    withings.get_activities_in_period.return_value = load_activity_fixture()

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.henk_steps_today")


async def test_activity_sensors_respect_timezone(
    hass: HomeAssistant,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test activity sensors use HA timezone instead of system timezone."""
    await hass.config.async_set_time_zone("Asia/Tokyo")
    freezer.move_to("2023-10-20T20:00:00+00:00")
    await setup_integration(hass, polling_config_entry, False)

    state = hass.states.get("sensor.henk_steps_today")
    assert state is not None
    assert state.state == "1155"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sleep_sensors_created_when_existed(
    hass: HomeAssistant,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test sleep sensors will be added if they existed before."""
    await setup_integration(hass, polling_config_entry, False)

    assert hass.states.get("sensor.henk_deep_sleep")
    assert hass.states.get("sensor.henk_deep_sleep").state != STATE_UNKNOWN

    withings.get_sleep_summary_since.return_value = []

    await hass.config_entries.async_reload(polling_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.henk_deep_sleep").state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sleep_sensors_created_when_receive_sleep_data(
    hass: HomeAssistant,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sleep sensors will be added if we receive sleep data."""
    withings.get_sleep_summary_since.return_value = []
    await setup_integration(hass, polling_config_entry, False)

    assert hass.states.get("sensor.henk_deep_sleep") is None

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.henk_deep_sleep") is None

    withings.get_sleep_summary_since.return_value = load_sleep_fixture()

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.henk_deep_sleep")


async def test_workout_sensors_created_when_existed(
    hass: HomeAssistant,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test workout sensors will be added if they existed before."""
    await setup_integration(hass, polling_config_entry, False)

    assert hass.states.get("sensor.henk_last_workout_type")
    assert hass.states.get("sensor.henk_last_workout_type").state != STATE_UNKNOWN

    withings.get_workouts_in_period.return_value = []

    await hass.config_entries.async_reload(polling_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.henk_last_workout_type").state == STATE_UNKNOWN


async def test_workout_sensors_created_when_receive_workout_data(
    hass: HomeAssistant,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test workout sensors will be added if we receive workout data."""
    withings.get_workouts_in_period.return_value = []
    await setup_integration(hass, polling_config_entry, False)

    assert hass.states.get("sensor.henk_last_workout_type") is None

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.henk_last_workout_type") is None

    withings.get_workouts_in_period.return_value = load_workout_fixture()

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.henk_last_workout_type")


async def test_warning_if_no_entities_created(
    hass: HomeAssistant,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test we log a warning if no entities are created at startup."""
    withings.get_workouts_in_period.return_value = []
    withings.get_goals.return_value = Goals(None, None, None)
    withings.get_measurement_in_period.return_value = []
    withings.get_sleep_summary_since.return_value = []
    withings.get_activities_since.return_value = []
    await setup_integration(hass, polling_config_entry, False)

    assert "No data found for Withings entry" in caplog.text


async def test_device_sensors_created_when_device_data_received(
    hass: HomeAssistant,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device sensors will be added if we receive device data."""
    withings.get_devices.return_value = []
    await setup_integration(hass, polling_config_entry, False)

    assert hass.states.get("sensor.body_battery") is None

    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.body_battery") is None

    withings.get_devices.return_value = load_device_fixture()

    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.body_battery")
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, "f998be4b9ccc9e136fd8cd8e8e344c31ec3b271d"),
        polling_config_entry.entry_id,
    )

    withings.get_devices.return_value = []

    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.body_battery") is None
    assert not device_registry.async_get_device_by_identifier(
        (DOMAIN, "f998be4b9ccc9e136fd8cd8e8e344c31ec3b271d"),
        polling_config_entry.entry_id,
    )


async def test_device_two_config_entries(
    hass: HomeAssistant,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
    second_polling_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test device sensors will be added for one config entry only at a time."""
    await setup_integration(hass, polling_config_entry, False)

    assert hass.states.get("sensor.body_battery") is not None

    second_polling_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(second_polling_config_entry.entry_id)

    assert hass.states.get("sensor.not_henk_temperature") is not None

    assert "Platform withings does not generate unique IDs" not in caplog.text

    await hass.config_entries.async_unload(polling_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.body_battery").state == STATE_UNAVAILABLE

    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.body_battery").state != STATE_UNAVAILABLE

    await hass.config_entries.async_setup(polling_config_entry.entry_id)
    await hass.async_block_till_done()

    assert "Platform withings does not generate unique IDs" not in caplog.text


async def test_old_device_removal_only_removes_own_device(
    hass: HomeAssistant,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
    second_polling_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Removing an old device only removes the processing entry's own device.

    Two config entries can each own a device registry entry for the same shared sub-device.
    When the sub-device disappears from one entry, it must remove its own device, not
    another entry's device sharing the identifier.
    """
    identifiers = {(DOMAIN, "f998be4b9ccc9e136fd8cd8e8e344c31ec3b271d")}

    def _device_for_entry(entry: MockConfigEntry) -> dr.DeviceEntry | None:
        return next(
            (
                device
                for device in device_registry.async_get_devices(identifiers=identifiers)
                if device.config_entry_id == entry.entry_id
            ),
            None,
        )

    # The first entry creates the sub-device and owns its device registry entry.
    await setup_integration(hass, polling_config_entry, False)
    assert _device_for_entry(polling_config_entry) is not None

    # Unload it, then set up a second entry: with the first entry unloaded it no longer
    # provides the sub-device, so the second entry creates and owns its own device.
    await hass.config_entries.async_unload(polling_config_entry.entry_id)
    await hass.async_block_till_done()

    second_polling_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(second_polling_config_entry.entry_id)
    await hass.async_block_till_done()

    assert _device_for_entry(polling_config_entry) is not None
    assert _device_for_entry(second_polling_config_entry) is not None

    # The sub-device disappears from the (still loaded) second entry's data.
    withings.get_devices.return_value = []
    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Only the second entry's own device was removed; the first entry's remains.
    assert _device_for_entry(second_polling_config_entry) is None
    assert _device_for_entry(polling_config_entry) is not None
