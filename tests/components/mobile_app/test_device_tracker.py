"""Test mobile app device tracker."""

from http import HTTPStatus
from typing import Any

from aiohttp.test_utils import TestClient
import pytest

from homeassistant.components import zone
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.restore_state import STORAGE_KEY as RESTORE_STATE_KEY
from homeassistant.setup import async_setup_component

from tests.common import (
    async_mock_restore_state_shutdown_restart,
    mock_restore_cache,
    mock_restore_cache_with_extra_data,
)


@pytest.fixture
async def setup_zone(hass: HomeAssistant) -> None:
    """Set up a zone for testing."""
    await async_setup_component(
        hass,
        zone.DOMAIN,
        {
            "zone": [
                {
                    "name": "Home",
                    "latitude": 10.0,
                    "longitude": 20.0,
                    "radius": 250,
                },
                {
                    "name": "Office",
                    "latitude": 20.0,
                    "longitude": 30.0,
                    "radius": 250,
                },
                {
                    "name": "School",
                    "latitude": 30.0,
                    "longitude": 40.0,
                    "radius": 250,
                },
            ]
        },
    )
    await hass.async_block_till_done()


@pytest.mark.usefixtures("setup_zone")
@pytest.mark.parametrize(
    ("extra_webhook_data", "expected_attributes", "expected_state"),
    [
        # Send coordinates + location_name: Location name has precedence
        (
            {"gps": [10, 20], "location_name": "home"},
            {
                "latitude": 10,
                "longitude": 20,
                "gps_accuracy": 30,
                "in_zones": ["zone.home"],
            },
            "home",
        ),
        (
            {"gps": [20, 30], "location_name": "office"},
            {
                "latitude": 20,
                "longitude": 30,
                "gps_accuracy": 30,
                "in_zones": ["zone.office"],
            },
            "Office",
        ),
        (
            {"gps": [30, 40], "location_name": "school"},
            {
                "latitude": 30,
                "longitude": 40,
                "gps_accuracy": 30,
                "in_zones": ["zone.school"],
            },
            "School",
        ),
        # Send wrong coordinates + location_name: Location name has precedence
        (
            {"gps": [10, 10], "location_name": "home"},
            {"latitude": 10, "longitude": 10, "gps_accuracy": 30, "in_zones": []},
            "home",
        ),
        (
            {"gps": [10, 10], "location_name": "office"},
            {"latitude": 10, "longitude": 10, "gps_accuracy": 30, "in_zones": []},
            "Office",
        ),
        (
            {"gps": [10, 10], "location_name": "school"},
            {"latitude": 10, "longitude": 10, "gps_accuracy": 30, "in_zones": []},
            "School",
        ),
        # Send location_name only
        ({"location_name": "home"}, {"in_zones": []}, "home"),
        ({"location_name": "office"}, {"in_zones": []}, "Office"),
        ({"location_name": "school"}, {"in_zones": []}, "School"),
        ({"location_name": "no_such_zone"}, {"in_zones": []}, "no_such_zone"),
        # Send coordinates only - location is determined by coordinates
        (
            {"gps": [10, 20]},
            {
                "latitude": 10,
                "longitude": 20,
                "gps_accuracy": 30,
                "in_zones": ["zone.home"],
            },
            "home",
        ),
        (
            {"gps": [20, 30]},
            {
                "latitude": 20,
                "longitude": 30,
                "gps_accuracy": 30,
                "in_zones": ["zone.office"],
            },
            "Office",
        ),
        (
            {"gps": [30, 40]},
            {
                "latitude": 30,
                "longitude": 40,
                "gps_accuracy": 30,
                "in_zones": ["zone.school"],
            },
            "School",
        ),
        # Send in_zones only - first zone determines state
        (
            {"in_zones": ["zone.home"]},
            {"in_zones": ["zone.home"]},
            "home",
        ),
        (
            {"in_zones": ["zone.office"]},
            {"in_zones": ["zone.office"]},
            "Office",
        ),
        (
            {"in_zones": ["zone.home", "zone.office"]},
            {"in_zones": ["zone.home", "zone.office"]},
            "home",
        ),
        # Empty in_zones list - not_home
        (
            {"in_zones": []},
            {"in_zones": []},
            "not_home",
        ),
        # in_zones + location_name: in_zones wins, location_name ignored
        (
            {"in_zones": ["zone.office"], "location_name": "home"},
            {"in_zones": ["zone.office"]},
            "Office",
        ),
        # in_zones with empty list still suppresses location_name
        (
            {"in_zones": [], "location_name": "home"},
            {"in_zones": []},
            "not_home",
        ),
        # in_zones + gps: in_zones wins, gps coordinates still reported as attributes
        (
            {"gps": [10, 20], "in_zones": ["zone.school"]},
            {
                "latitude": 10,
                "longitude": 20,
                "gps_accuracy": 30,
                "in_zones": ["zone.school"],
            },
            "School",
        ),
    ],
)
async def test_sending_location(
    hass: HomeAssistant,
    create_registrations: tuple[dict[str, Any], dict[str, Any]],
    webhook_client: TestClient,
    extra_webhook_data: dict[str, Any],
    expected_attributes: dict[str, Any],
    expected_state: str,
) -> None:
    """Test sending a location via a webhook."""
    resp = await webhook_client.post(
        f"/api/webhook/{create_registrations[1]['webhook_id']}",
        json={
            "type": "update_location",
            "data": {
                "gps_accuracy": 30,
                "battery": 40,
                "altitude": 50,
                "course": 60,
                "speed": 70,
                "vertical_accuracy": 80,
            }
            | extra_webhook_data,
        },
    )

    assert resp.status == HTTPStatus.OK
    await hass.async_block_till_done()
    state = hass.states.get("device_tracker.test_1_2")
    assert state is not None
    assert state.name == "Test 1"
    assert state.state == expected_state
    assert (
        state.attributes
        == {
            "friendly_name": "Test 1",
            "source_type": "gps",
            "battery_level": 40,
            "altitude": 50.0,
            "course": 60,
            "speed": 70,
            "vertical_accuracy": 80,
        }
        | expected_attributes
    )

    resp = await webhook_client.post(
        f"/api/webhook/{create_registrations[1]['webhook_id']}",
        json={
            "type": "update_location",
            "data": {
                "gps": [1, 2],
                "gps_accuracy": 3,
                "battery": 4,
                "altitude": 5,
                "course": 6,
                "speed": 7,
                "vertical_accuracy": 8,
                "location_name": "",
            },
        },
    )

    assert resp.status == HTTPStatus.OK
    await hass.async_block_till_done()
    state = hass.states.get("device_tracker.test_1_2")
    assert state is not None
    assert state.state == "not_home"
    assert state.attributes == {
        "friendly_name": "Test 1",
        "source_type": "gps",
        "latitude": 1.0,
        "longitude": 2.0,
        "gps_accuracy": 3,
        "battery_level": 4,
        "altitude": 5.0,
        "course": 6,
        "speed": 7,
        "vertical_accuracy": 8,
        "in_zones": [],
    }


async def test_restoring_location(
    hass: HomeAssistant,
    create_registrations: tuple[dict[str, Any], dict[str, Any]],
    webhook_client: TestClient,
) -> None:
    """Test sending a location via a webhook."""
    resp = await webhook_client.post(
        f"/api/webhook/{create_registrations[1]['webhook_id']}",
        json={
            "type": "update_location",
            "data": {
                "gps": [10, 20],
                "gps_accuracy": 30,
                "battery": 40,
                "altitude": 50,
                "course": 60,
                "speed": 70,
                "vertical_accuracy": 80,
            },
        },
    )

    assert resp.status == HTTPStatus.OK
    await hass.async_block_till_done()
    state_1 = hass.states.get("device_tracker.test_1_2")
    assert state_1 is not None

    config_entry = hass.config_entries.async_entries("mobile_app")[1]

    # mobile app doesn't support unloading, so we just reload device tracker
    await hass.config_entries.async_forward_entry_unload(
        config_entry, Platform.DEVICE_TRACKER
    )
    await hass.config_entries.async_forward_entry_setups(
        config_entry, [Platform.DEVICE_TRACKER]
    )
    await hass.async_block_till_done()

    state_2 = hass.states.get("device_tracker.test_1_2")
    assert state_2 is not None

    assert state_1 is not state_2
    assert state_2.name == "Test 1"
    assert state_2.state == "not_home"
    assert state_2.attributes["source_type"] == "gps"
    assert state_2.attributes["latitude"] == 10
    assert state_2.attributes["longitude"] == 20
    assert state_2.attributes["gps_accuracy"] == 30
    assert state_2.attributes["battery_level"] == 40
    assert state_2.attributes["altitude"] == 50
    assert state_2.attributes["course"] == 60
    assert state_2.attributes["speed"] == 70
    assert state_2.attributes["vertical_accuracy"] == 80


@pytest.mark.usefixtures("setup_zone")
@pytest.mark.parametrize(
    (
        "extra_webhook_data",
        "expected_saved_state",
        "expected_saved_attributes",
        "expected_extra_data",
    ),
    [
        # Coordinates inside a zone
        (
            {"gps": [10, 20]},
            "home",
            {
                "friendly_name": "Test 1",
                "source_type": "gps",
                "battery_level": 40,
                "altitude": 50.0,
                "course": 60,
                "speed": 70,
                "vertical_accuracy": 80,
                "latitude": 10.0,
                "longitude": 20.0,
                "gps_accuracy": 30,
                "in_zones": ["zone.home"],
            },
            {
                "data": {
                    "gps_accuracy": 30,
                    "battery": 40,
                    "altitude": 50.0,
                    "course": 60,
                    "speed": 70,
                    "vertical_accuracy": 80,
                    "gps": [10, 20],
                }
            },
        ),
        # location_name only
        (
            {"location_name": "office"},
            "Office",
            {
                "friendly_name": "Test 1",
                "source_type": "gps",
                "battery_level": 40,
                "altitude": 50.0,
                "course": 60,
                "speed": 70,
                "vertical_accuracy": 80,
                "in_zones": [],
            },
            {
                "data": {
                    "gps_accuracy": 30,
                    "battery": 40,
                    "altitude": 50.0,
                    "course": 60,
                    "speed": 70,
                    "vertical_accuracy": 80,
                    "location_name": "office",
                }
            },
        ),
        # in_zones only
        (
            {"in_zones": ["zone.office"]},
            "Office",
            {
                "friendly_name": "Test 1",
                "source_type": "gps",
                "battery_level": 40,
                "altitude": 50.0,
                "course": 60,
                "speed": 70,
                "vertical_accuracy": 80,
                "in_zones": ["zone.office"],
            },
            {
                "data": {
                    "gps_accuracy": 30,
                    "battery": 40,
                    "altitude": 50.0,
                    "course": 60,
                    "speed": 70,
                    "vertical_accuracy": 80,
                    "in_zones": ["zone.office"],
                }
            },
        ),
    ],
)
async def test_saving_state(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    create_registrations: tuple[dict[str, Any], dict[str, Any]],
    webhook_client: TestClient,
    extra_webhook_data: dict[str, Any],
    expected_saved_state: str,
    expected_saved_attributes: dict[str, Any],
    expected_extra_data: dict[str, Any],
) -> None:
    """Test that the entity state is correctly persisted to storage."""
    resp = await webhook_client.post(
        f"/api/webhook/{create_registrations[1]['webhook_id']}",
        json={
            "type": "update_location",
            "data": {
                "gps_accuracy": 30,
                "battery": 40,
                "altitude": 50,
                "course": 60,
                "speed": 70,
                "vertical_accuracy": 80,
            }
            | extra_webhook_data,
        },
    )
    assert resp.status == HTTPStatus.OK
    await hass.async_block_till_done()

    await async_mock_restore_state_shutdown_restart(hass)

    saved = next(
        item
        for item in hass_storage[RESTORE_STATE_KEY]["data"]
        if item["state"]["entity_id"] == "device_tracker.test_1_2"
    )
    assert saved["state"]["state"] == expected_saved_state
    assert saved["state"]["attributes"] == expected_saved_attributes
    assert saved["extra_data"] == expected_extra_data


@pytest.mark.usefixtures("setup_zone")
@pytest.mark.parametrize(
    ("restored_data", "expected_state", "expected_attributes"),
    [
        # Coordinates inside the home zone
        (
            {
                "gps": [10.0, 20.0],
                "gps_accuracy": 30,
                "battery": 40,
                "altitude": 50.0,
                "course": 60,
                "speed": 70,
                "vertical_accuracy": 80,
            },
            "home",
            {
                "friendly_name": "Test 1",
                "source_type": "gps",
                "latitude": 10.0,
                "longitude": 20.0,
                "gps_accuracy": 30,
                "battery_level": 40,
                "altitude": 50.0,
                "course": 60,
                "speed": 70,
                "vertical_accuracy": 80,
                "in_zones": ["zone.home"],
            },
        ),
        # Coordinates outside any zone
        (
            {
                "gps": [1.0, 2.0],
                "gps_accuracy": 3,
                "battery": 4,
            },
            "not_home",
            {
                "friendly_name": "Test 1",
                "source_type": "gps",
                "latitude": 1.0,
                "longitude": 2.0,
                "gps_accuracy": 3,
                "battery_level": 4,
                "in_zones": [],
            },
        ),
        # Last update was a named location only (no coords)
        (
            {
                "location_name": "office",
                "battery": 40,
                "altitude": 50.0,
                "course": 60,
                "speed": 70,
                "vertical_accuracy": 80,
            },
            "Office",
            {
                "friendly_name": "Test 1",
                "source_type": "gps",
                "battery_level": 40,
                "altitude": 50.0,
                "course": 60,
                "speed": 70,
                "vertical_accuracy": 80,
                "in_zones": [],
            },
        ),
        # Last update was an in_zones list (no coords)
        (
            {
                "in_zones": ["zone.office"],
                "battery": 40,
                "altitude": 50.0,
                "course": 60,
                "speed": 70,
                "vertical_accuracy": 80,
            },
            "Office",
            {
                "friendly_name": "Test 1",
                "source_type": "gps",
                "battery_level": 40,
                "altitude": 50.0,
                "course": 60,
                "speed": 70,
                "vertical_accuracy": 80,
                "in_zones": ["zone.office"],
            },
        ),
        # Empty in_zones list - not_home
        (
            {
                "in_zones": [],
                "battery": 40,
            },
            "not_home",
            {
                "friendly_name": "Test 1",
                "source_type": "gps",
                "battery_level": 40,
                "in_zones": [],
            },
        ),
    ],
)
async def test_restoring_state(
    hass: HomeAssistant,
    create_registrations: tuple[dict[str, Any], dict[str, Any]],
    restored_data: dict[str, Any],
    expected_state: str,
    expected_attributes: dict[str, Any],
) -> None:
    """Test that the entity restores state from storage."""
    config_entry = hass.config_entries.async_entries("mobile_app")[1]
    await hass.config_entries.async_unload(config_entry.entry_id)

    mock_restore_cache_with_extra_data(
        hass,
        [(State("device_tracker.test_1_2", ""), {"data": restored_data})],
    )

    # Reload the config entry
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.test_1_2")
    assert state is not None
    assert state.state == expected_state
    assert state.attributes == expected_attributes


@pytest.mark.usefixtures("setup_zone")
@pytest.mark.parametrize(
    ("restored_state", "restored_attributes", "expected_state", "expected_attributes"),
    [
        # Full attributes, coordinates inside the home zone
        (
            "home",
            {
                "source_type": "gps",
                "latitude": 10.0,
                "longitude": 20.0,
                "gps_accuracy": 30,
                "battery_level": 40,
                "altitude": 50.0,
                "course": 60,
                "speed": 70,
                "vertical_accuracy": 80,
            },
            "home",
            {
                "friendly_name": "Test 1",
                "source_type": "gps",
                "latitude": 10.0,
                "longitude": 20.0,
                "gps_accuracy": 30,
                "battery_level": 40,
                "altitude": 50.0,
                "course": 60,
                "speed": 70,
                "vertical_accuracy": 80,
                "in_zones": ["zone.home"],
            },
        ),
        # Coordinates outside any zone
        (
            "not_home",
            {
                "source_type": "gps",
                "latitude": 1.0,
                "longitude": 2.0,
                "gps_accuracy": 3,
                "battery_level": 4,
            },
            "not_home",
            {
                "friendly_name": "Test 1",
                "source_type": "gps",
                "latitude": 1.0,
                "longitude": 2.0,
                "gps_accuracy": 3,
                "battery_level": 4,
                "in_zones": [],
            },
        ),
        # Last update was a named location only (no coords). The location name
        # is not persisted, so the entity falls back to "unknown" on restore.
        (
            "Office",
            {
                "source_type": "gps",
                "battery_level": 40,
                "altitude": 50.0,
                "course": 60,
                "speed": 70,
                "vertical_accuracy": 80,
                "in_zones": [],
            },
            "unknown",
            {
                "friendly_name": "Test 1",
                "source_type": "gps",
                "battery_level": 40,
                "altitude": 50.0,
                "course": 60,
                "speed": 70,
                "vertical_accuracy": 80,
                "in_zones": [],
            },
        ),
    ],
)
async def test_restoring_state_legacy_fallback(
    hass: HomeAssistant,
    create_registrations: tuple[dict[str, Any], dict[str, Any]],
    restored_state: str,
    restored_attributes: dict[str, Any],
    expected_state: str,
    expected_attributes: dict[str, Any],
) -> None:
    """Test fallback to legacy state attributes when no extra_data is stored.

    Covers entries persisted before MobileAppDeviceTrackerExtraStoredData existed.
    """
    config_entry = hass.config_entries.async_entries("mobile_app")[1]
    await hass.config_entries.async_unload(config_entry.entry_id)

    mock_restore_cache(
        hass,
        [State("device_tracker.test_1_2", restored_state, restored_attributes)],
    )

    # Reload the config entry
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.test_1_2")
    assert state is not None
    assert state.state == expected_state
    assert state.attributes == expected_attributes


@pytest.mark.parametrize(
    "invalid_data",
    [
        # gps without the required gps_accuracy companion
        {"gps": [10.0, 20.0]},
        # battery rejected by cv.positive_int
        {"battery": -1},
        # gps_accuracy rejected by cv.positive_float
        {"gps_accuracy": "not-a-number"},
        # in_zones contains a non-zone entity_id
        {"in_zones": ["sensor.foo"]},
    ],
)
async def test_restoring_state_invalid_extra_data(
    hass: HomeAssistant,
    create_registrations: tuple[dict[str, Any], dict[str, Any]],
    caplog: pytest.LogCaptureFixture,
    invalid_data: dict[str, Any],
) -> None:
    """Test that invalid extra_data is rejected without falling back to state attrs.

    Invalid extra_data signals corrupt persisted data — discard it rather than
    restore from the (separately saved) state attributes, which could be stale
    or inconsistent with the rejected payload.
    """
    config_entry = hass.config_entries.async_entries("mobile_app")[1]

    await hass.config_entries.async_unload(config_entry.entry_id)

    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(
                    "device_tracker.test_1_2",
                    "not_home",
                    {
                        "source_type": "gps",
                        "latitude": 1.0,
                        "longitude": 2.0,
                        "gps_accuracy": 3,
                        "battery_level": 4,
                    },
                ),
                {"data": invalid_data},
            )
        ],
    )

    # Reload the config entry
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert "Discarding invalid restored device tracker data" in caplog.text

    state = hass.states.get("device_tracker.test_1_2")
    assert state is not None
    assert state.state == "unknown"
    assert state.attributes == {
        "friendly_name": "Test 1",
        "source_type": "gps",
        "in_zones": [],
    }
