"""Sensor tests of Electrolux integration."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import get_appliance_id, merge_dict_recursive, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.electrolux.PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.mark.usefixtures("appliances")
async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test states of the sensor."""
    freezer.move_to("2026-09-29 12:00:00+00:00")
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    (
        "iso_string_now",
        "appliance_fixture",
        "entity_id",
        "appliance_state",
        "expected_state",
    ),
    [
        # oven start_at sensor tests
        (
            "2026-09-29 12:00:00+00:00",
            "fenix_oven",
            "sensor.fenix_start_at",
            {"applianceState": "DELAYED_START", "startTime": 600},
            dt_util.parse_datetime("2026-09-29 12:10:00+00:00").isoformat(),
        ),
        (
            "2026-09-29 12:00:10+00:00",
            "fenix_oven",
            "sensor.fenix_start_at",
            {"applianceState": "DELAYED_START", "startTime": 600},
            dt_util.parse_datetime("2026-09-29 12:10:00+00:00").isoformat(),
        ),
        (
            "2026-09-29 12:00:00+00:00",
            "fenix_oven",
            "sensor.fenix_start_at",
            {"applianceState": "RUNNING"},
            "unknown",
        ),
        (
            "2026-09-29 12:00:00+00:00",
            "fenix_oven",
            "sensor.fenix_start_at",
            {"applianceState": "RUNNING", "startTime": 600},
            "unknown",
        ),
        (
            "2026-09-29 12:00:00+00:00",
            "fenix_oven",
            "sensor.fenix_start_at",
            {"applianceState": "DELAYED_START", "startTime": -1},
            "unknown",
        ),
        # care appliance (dishwasher) start_at sensor tests
        (
            "2026-09-29 12:00:00+00:00",
            "electrolux_dishwasher",
            "sensor.dishwasher_start_at",
            {"applianceState": "DELAYED_START", "startTime": 600},
            dt_util.parse_datetime("2026-09-29 12:10:00+00:00").isoformat(),
        ),
        (
            "2026-09-29 12:00:00+00:00",
            "electrolux_dishwasher",
            "sensor.dishwasher_start_at",
            {"applianceState": "DELAYED_START", "stopTime": 1800, "timeToEnd": 600},
            dt_util.parse_datetime("2026-09-29 12:20:00+00:00").isoformat(),
        ),
        (
            "2026-09-29 12:00:10+00:00",
            "electrolux_dishwasher",
            "sensor.dishwasher_start_at",
            {"applianceState": "DELAYED_START", "startTime": 600},
            dt_util.parse_datetime("2026-09-29 12:10:00+00:00").isoformat(),
        ),
        (
            "2026-09-29 12:00:00+00:00",
            "electrolux_dishwasher",
            "sensor.dishwasher_start_at",
            {"applianceState": "RUNNING"},
            "unknown",
        ),
        (
            "2026-09-29 12:00:00+00:00",
            "electrolux_dishwasher",
            "sensor.dishwasher_start_at",
            {"applianceState": "RUNNING", "startTime": 600},
            "unknown",
        ),
        (
            "2026-09-29 12:00:00+00:00",
            "electrolux_dishwasher",
            "sensor.dishwasher_start_at",
            {"applianceState": "DELAYED_START", "startTime": -1},
            "unknown",
        ),
        # care appliance (dishwasher) end_at sensor tests
        (
            "2026-09-29 12:00:00+00:00",
            "electrolux_dishwasher",
            "sensor.dishwasher_end_at",
            {"applianceState": "DELAYED_START", "stopTime": 600},
            dt_util.parse_datetime("2026-09-29 12:10:00+00:00").isoformat(),
        ),
        (
            "2026-09-29 12:00:00+00:00",
            "electrolux_dishwasher",
            "sensor.dishwasher_end_at",
            {"applianceState": "DELAYED_START", "startTime": 600, "timeToEnd": 600},
            dt_util.parse_datetime("2026-09-29 12:20:00+00:00").isoformat(),
        ),
        (
            "2026-09-29 12:00:10+00:00",
            "electrolux_dishwasher",
            "sensor.dishwasher_end_at",
            {"applianceState": "DELAYED_START", "stopTime": 600},
            dt_util.parse_datetime("2026-09-29 12:10:00+00:00").isoformat(),
        ),
        (
            "2026-09-29 12:00:00+00:00",
            "electrolux_dishwasher",
            "sensor.dishwasher_end_at",
            {"applianceState": "RUNNING", "timeToEnd": 720},
            dt_util.parse_datetime("2026-09-29 12:12:00+00:00").isoformat(),
        ),
        (
            "2026-09-29 12:00:00+00:00",
            "electrolux_dishwasher",
            "sensor.dishwasher_end_at",
            {"applianceState": "RUNNING", "startTime": 600, "timeToEnd": -1},
            "unknown",
        ),
        (
            "2026-09-29 12:00:00+00:00",
            "electrolux_dishwasher",
            "sensor.dishwasher_end_at",
            {"applianceState": "PAUSED", "timeToEnd": 720},
            "unknown",
        ),
    ],
)
async def test_timestamp_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    appliances: AsyncMock,
    iso_string_now: str,
    appliance_fixture: str,
    entity_id: str,
    appliance_state: dict[str, Any],
    expected_state: Any,
) -> None:
    """Test states of the sensor."""
    freezer.move_to(iso_string_now)

    appliance_id = get_appliance_id(appliance_fixture)

    state = await appliances.get_appliance_state(appliance_id)
    state.properties["reported"] = merge_dict_recursive(
        state.properties["reported"], appliance_state
    )

    appliances.get_appliance_state.side_effect = None
    appliances.get_appliance_state.return_value = state

    await setup_integration(hass, mock_config_entry)

    ha_state = hass.states.get(entity_id)
    assert ha_state
    assert ha_state.state == expected_state, (
        f"Expected state for {entity_id} to be {expected_state}, but got {ha_state.state}"
    )


@pytest.mark.parametrize(
    (
        "appliance_fixture",
        "entity_id",
        "appliance_state",
        "expected_state",
        "unit",
    ),
    [
        # oven duration sensors
        (
            "fenix_oven",
            "sensor.fenix_running_time",
            {"runningTime": 1800},
            "0.5",
            "h",
        ),
        (
            "fenix_oven",
            "sensor.fenix_time_left",
            {"timeToEnd": 900},
            "0.25",
            "h",
        ),
        # care appliance (dishwasher) duration sensor(s)
        (
            "electrolux_dishwasher",
            "sensor.dishwasher_time_left",
            {"applianceState": "RUNNING", "timeToEnd": 900},
            "0.25",
            "h",
        ),
        (
            "electrolux_dishwasher",
            "sensor.dishwasher_time_left",
            {"applianceState": "PAUSED", "timeToEnd": 900},
            "0.25",
            "h",
        ),
    ],
)
async def test_duration_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    appliances: AsyncMock,
    appliance_fixture: str,
    entity_id: str,
    appliance_state: dict[str, Any],
    expected_state: Any,
    unit: str,
) -> None:
    """Test states of the sensor."""

    appliance_id = get_appliance_id(appliance_fixture)

    state = await appliances.get_appliance_state(appliance_id)
    state.properties["reported"] = merge_dict_recursive(
        state.properties["reported"], appliance_state
    )

    appliances.get_appliance_state.side_effect = None
    appliances.get_appliance_state.return_value = state

    await setup_integration(hass, mock_config_entry)

    ha_state = hass.states.get(entity_id)
    assert ha_state
    assert ha_state.state == expected_state, (
        f"Expected state for {entity_id} to be {expected_state}, but got {ha_state.state}"
    )
    ha_unit = ha_state.attributes.get("unit_of_measurement")
    assert ha_unit == unit, (
        f"Expected unit for {entity_id} to be {unit}, but got {ha_unit}"
    )
