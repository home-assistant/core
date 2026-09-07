"""Tests for LG ThinQ oven remaining-time sensors."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lg_thinq.const import DOMAIN
from homeassistant.components.lg_thinq.coordinator import DeviceDataUpdateCoordinator
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
    snapshot_platform,
)

pytestmark = pytest.mark.freeze_time("2026-09-07T18:30:00+00:00")

START = datetime(2026, 9, 7, 18, 30, tzinfo=UTC)
UPPER_ENTITY_ID = "sensor.test_oven_upper_remaining_time"
LOWER_ENTITY_ID = "sensor.test_oven_lower_remaining_time"


@pytest.fixture
def oven_api(mock_thinq_api: AsyncMock) -> AsyncMock:
    """Provide a synthetic two-cavity oven through the real ThinQ bridge."""
    mock_thinq_api.async_get_device_list.return_value = [
        load_json_object_fixture("oven/device.json", DOMAIN)
    ]
    mock_thinq_api.async_get_device_profile.return_value = load_json_object_fixture(
        "oven/profile.json", DOMAIN
    )
    mock_thinq_api.async_get_device_status.return_value = load_json_array_fixture(
        "oven/status.json", DOMAIN
    )
    mock_thinq_api.async_get_device_energy_profile.return_value = None
    return mock_thinq_api


@pytest.fixture
async def oven_coordinator(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, oven_api: AsyncMock
) -> DeviceDataUpdateCoordinator:
    """Set up the oven's sensor platform."""
    with patch("homeassistant.components.lg_thinq.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)
    return next(iter(mock_config_entry.runtime_data.coordinators.values()))


@pytest.mark.usefixtures("oven_coordinator")
async def test_oven_sensor_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Snapshot the existing status entities and added timer entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        pytest.param(600, "2026-09-07T18:41:00+00:00", id="extend"),
        pytest.param(300, "2026-09-07T18:36:00+00:00", id="shorten"),
        pytest.param(0, STATE_UNKNOWN, id="cancel"),
    ],
)
async def test_adjust_oven_timer(
    hass: HomeAssistant,
    oven_coordinator: DeviceDataUpdateCoordinator,
    freezer: FrozenDateTimeFactory,
    seconds: int,
    expected: str,
) -> None:
    """A cook timer can be adjusted without changing the cooking status."""
    freezer.move_to(START + timedelta(seconds=30))
    oven_coordinator.handle_update_status(
        [
            {
                "location": {"locationName": "UPPER"},
                "timer": {"remainMinute": 9, "remainSecond": 30},
            }
        ]
    )
    freezer.move_to(START + timedelta(minutes=1))
    oven_coordinator.handle_update_status(
        [
            {
                "location": {"locationName": "UPPER"},
                "timer": {
                    "remainMinute": seconds // 60,
                    "remainSecond": seconds % 60,
                },
            }
        ]
    )
    assert hass.states.get(UPPER_ENTITY_ID).state == expected
    assert hass.states.get(LOWER_ENTITY_ID).state == "2026-09-07T18:40:00+00:00"


async def test_countdown_is_stable(
    hass: HomeAssistant,
    oven_coordinator: DeviceDataUpdateCoordinator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Countdown reports and unrelated updates keep the original deadline."""
    initial_state = hass.states.get(UPPER_ENTITY_ID)
    freezer.move_to(START + timedelta(minutes=1, seconds=2))
    oven_coordinator.handle_update_status(
        [{"location": {"locationName": "UPPER"}, "timer": {"remainMinute": 9}}]
    )
    assert hass.states.get(UPPER_ENTITY_ID) == initial_state
    freezer.move_to(START + timedelta(minutes=2))
    oven_coordinator.handle_update_status(
        [{"location": {"locationName": "LOWER"}, "timer": {"remainMinute": 5}}]
    )
    assert hass.states.get(UPPER_ENTITY_ID) == initial_state
    assert hass.states.get(LOWER_ENTITY_ID).state == "2026-09-07T18:37:00+00:00"


@pytest.mark.parametrize("status", ["INITIAL", "DONE", "COOLING"])
async def test_inactive_oven_clears_cached_timer(
    hass: HomeAssistant,
    oven_coordinator: DeviceDataUpdateCoordinator,
    status: str,
) -> None:
    """An inactive cavity must not display a cached nonzero timer."""
    oven_coordinator.handle_update_status(
        [{"location": {"locationName": "UPPER"}, "runState": {"currentState": status}}]
    )
    assert hass.states.get(UPPER_ENTITY_ID).state == STATE_UNKNOWN
    assert hass.states.get(LOWER_ENTITY_ID).state == "2026-09-07T18:40:00+00:00"


@pytest.mark.parametrize("status", ["PREHEATING", "COOKING_IN_PROGRESS"])
async def test_start_timer_while_oven_is_active(
    hass: HomeAssistant,
    oven_coordinator: DeviceDataUpdateCoordinator,
    freezer: FrozenDateTimeFactory,
    status: str,
) -> None:
    """A timer starts after an untimed cook or a cancellation."""
    oven_coordinator.handle_update_status(
        [
            {
                "location": {"locationName": "UPPER"},
                "runState": {"currentState": status},
                "timer": {"remainMinute": 0},
            }
        ]
    )
    assert hass.states.get(UPPER_ENTITY_ID).state == STATE_UNKNOWN
    freezer.move_to(START + timedelta(minutes=14))
    oven_coordinator.handle_update_status(
        [{"location": {"locationName": "UPPER"}, "timer": {"remainMinute": 10}}]
    )
    assert hass.states.get(UPPER_ENTITY_ID).state == "2026-09-07T18:54:00+00:00"


async def test_oven_without_timer_support(
    hass: HomeAssistant, oven_api: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Do not create a timer sensor for a cavity without readable timer fields."""
    oven_api.async_get_device_profile.return_value["property"][0].pop("timer")
    with patch("homeassistant.components.lg_thinq.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)
    assert hass.states.get(UPPER_ENTITY_ID) is None
    assert hass.states.get(LOWER_ENTITY_ID).state == "2026-09-07T18:40:00+00:00"


@pytest.mark.parametrize("missing_field", ["timer", "runState"])
async def test_missing_oven_data(
    hass: HomeAssistant,
    oven_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    missing_field: str,
) -> None:
    """Keep the deadline unknown until the timer and active status are known."""
    oven_api.async_get_device_status.return_value[0].pop(missing_field)
    with patch("homeassistant.components.lg_thinq.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)
    assert hass.states.get(UPPER_ENTITY_ID).state == STATE_UNKNOWN
    assert hass.states.get(LOWER_ENTITY_ID).state == "2026-09-07T18:40:00+00:00"
