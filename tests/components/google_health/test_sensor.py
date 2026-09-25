"""Tests for Google Health sensor platform."""

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from google_health_api.const import HealthApiScope
from google_health_api.model import (
    SLEEP,
    ListPairedDevicesResult,
    _ListPairedDevicesModel,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.google_health.const import DOMAIN
from homeassistant.components.google_health.coordinator import DEVICE_POLLING_INTERVAL
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)

from .conftest import _list_fixture, paired_devices_fixture

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("mock_google_health_client")
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
    mock_google_health_client.hydration_log.today.return_value = None
    mock_google_health_client.nutrition_log.today.return_value = None

    assert await integration_setup()

    steps_state = hass.states.get("sensor.google_health_steps")
    assert steps_state is not None
    assert steps_state.state == "0"

    distance_state = hass.states.get("sensor.google_health_distance")
    assert distance_state is not None
    assert distance_state.state == "0.0"

    active_calories_state = hass.states.get("sensor.google_health_active_calories")
    assert active_calories_state is not None
    assert active_calories_state.state == "0.0"

    total_calories_state = hass.states.get("sensor.google_health_total_calories")
    assert total_calories_state is not None
    assert total_calories_state.state == "0.0"

    floors_state = hass.states.get("sensor.google_health_floors")
    assert floors_state is not None
    assert floors_state.state == "0"

    hydration_state = hass.states.get("sensor.google_health_water_intake")
    assert hydration_state is not None
    assert hydration_state.state == "0.0"

    calories_consumed_state = hass.states.get("sensor.google_health_calories_consumed")
    assert calories_consumed_state is not None
    assert calories_consumed_state.state == "0.0"


async def test_sensor_empty_sleep(
    hass: HomeAssistant,
    mock_google_health_client: AsyncMock,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test sleep sensors when the sleep endpoint returns no data."""
    mock_google_health_client.sleep.list.return_value = MagicMock(data_points=[])

    assert await integration_setup()

    time_asleep_state = hass.states.get("sensor.google_health_time_asleep")
    assert time_asleep_state is not None
    assert time_asleep_state.state == "unknown"


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

    time_asleep_state = hass.states.get("sensor.google_health_time_asleep")
    assert time_asleep_state is not None
    assert time_asleep_state.state == "7.0"

    time_awake_state = hass.states.get("sensor.google_health_time_awake")
    assert time_awake_state is not None
    assert time_awake_state.state == "1.0"

    time_in_bed_state = hass.states.get("sensor.google_health_time_in_bed")
    assert time_in_bed_state is not None
    assert time_in_bed_state.state == "8.0"

    time_to_fall_asleep_state = hass.states.get(
        "sensor.google_health_time_to_fall_asleep"
    )
    assert time_to_fall_asleep_state is not None
    assert time_to_fall_asleep_state.state == "15"

    time_after_wakeup_state = hass.states.get(
        "sensor.google_health_time_after_waking_up"
    )
    assert time_after_wakeup_state is not None
    assert time_after_wakeup_state.state == "10"


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
                "sensor.google_health_water_intake": (pytest.approx(2.5), "L"),
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
                "sensor.google_health_water_intake": (
                    pytest.approx(84.54, abs=1e-1),
                    "fl. oz.",
                ),
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
        assert state.attributes.get("unit_of_measurement") == expected_unit


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
