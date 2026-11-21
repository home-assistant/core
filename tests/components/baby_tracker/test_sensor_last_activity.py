"""Tests for the last diaper, last feed, and last sleep sensors (state only)."""

from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_STATE_REPORTED
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from . import DIAPER, NOW, get_baby_device, tick
from .factories import BABY_THREE_ID, DEVICE_A, DEVICE_B, at, baby_payload, volume
from .fake_server import FakeServer

KEYS = (
    "last_diaper",
    "last_feed",
    "last_sleep",
)  # a pump belongs to the account, not a baby


BABY_THREE = baby_payload("Baby Three", BABY_THREE_ID)


def _entity_id(baby: str, key: str) -> str:
    return f"sensor.{baby}_{key}"


def _sensor_state(hass: HomeAssistant, baby: str, key: str):
    state = hass.states.get(_entity_id(baby, key))
    assert state is not None, f"{_entity_id(baby, key)} does not exist"
    return state


def _object_id(number: int) -> str:
    return f"A0000000-0000-4000-8000-{number:012d}"


@pytest.fixture(autouse=True)
def _start_at_now(freezer: FrozenDateTimeFactory) -> None:
    """Freeze the clock at NOW before anything is set up.

    Timers scheduled at setup then share the clock the tests move, so moving it forward and
    ticking reaches them the way it does in core's tests.
    """
    freezer.move_to(NOW)


async def test_the_last_diaper_shows_when_it_happened(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the last diaper sensor shows the newest diaper's time."""
    assert _sensor_state(hass, "baby_one", "last_diaper").state == at(0).isoformat()
    assert _sensor_state(hass, "baby_two", "last_diaper").state == at(10).isoformat()


async def test_a_feed_that_is_not_nursing_formula_or_pumped_is_ignored(
    hass: HomeAssistant, init_integration: MockConfigEntry, server: FakeServer
) -> None:
    """Test an unknown kind of feed doesn't count as the last feed."""
    server.add_record(
        DEVICE_A, "Formula", _object_id(33), when=at(10), amount=volume(2)
    )
    server.add_record(DEVICE_A, "OtherFeed", _object_id(34), when=at(99), amount=2.5)
    await tick(hass)
    assert _sensor_state(hass, "baby_one", "last_feed").state == at(10).isoformat()


async def test_a_baby_with_no_records_yet_still_gets_a_device_and_sensors(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    server: FakeServer,
) -> None:
    """Test a baby with no records gets a device and unknown sensors."""
    server.add_payload(DEVICE_A, BABY_THREE)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    device = get_baby_device(device_registry, BABY_THREE_ID)
    assert device is not None
    assert device.name == "Baby Three"
    for key in KEYS:
        assert _sensor_state(hass, "baby_three", key).state == "unknown"


async def test_babies_are_restored_from_saved_state_after_a_restart(
    hass: HomeAssistant, init_integration: MockConfigEntry, server: FakeServer
) -> None:
    """Test the babies come back from the saved state after a restart."""
    server.add_record(DEVICE_B, "Diaper", _object_id(72), when=at(300), baby=BABY_THREE)
    await tick(hass)
    assert await hass.config_entries.async_unload(init_integration.entry_id)
    assert await hass.config_entries.async_setup(init_integration.entry_id)
    await hass.async_block_till_done()

    for baby in ("baby_one", "baby_two", "baby_three"):
        assert _sensor_state(hass, baby, "last_diaper").state != "unknown"


async def test_a_refresh_with_nothing_new_writes_no_states(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test a refresh that finds nothing new writes no states."""
    reported: list[Event] = []

    @callback
    def record(event: Event) -> None:
        reported.append(event)

    @callback
    def is_ours(data: dict[str, Any]) -> bool:
        return data["entity_id"].split(".")[1].startswith(("baby_", "baby_tracker"))

    hass.bus.async_listen(EVENT_STATE_REPORTED, record, event_filter=is_ours)
    await tick(hass)
    assert reported == []


async def test_a_refresh_with_a_new_record_still_updates_the_sensor(
    hass: HomeAssistant, init_integration: MockConfigEntry, server: FakeServer
) -> None:
    """Test a refresh that finds a newer record updates the sensor."""
    server.add_record(
        "BBBBBBBB-0000-4000-8000-00000000000B",
        "Diaper",
        "D2000000-0000-4000-8000-000000000001",
        when=at(60),
    )
    await tick(hass)
    assert hass.states.get(DIAPER).state == at(60).isoformat()
