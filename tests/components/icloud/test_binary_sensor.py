"""Tests for the iCloud binary sensor platform."""

from collections.abc import Awaitable, Callable
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.typing import MagicMock

from homeassistant.components.icloud.const import ATTR_DEVICE_STATUS, DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DEVICE, FEATURES, LOCATION

LOCATION_UNIQUE_IDS = ["device1_location_current", "device1_location_accurate"]
LOCATING_UNIQUE_ID = "device1_locating"


async def _async_enable_entity(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    unique_id: str,
) -> None:
    """Enable a disabled by default binary sensor and reload the entry."""
    entity_id = entity_registry.async_get_entity_id("binary_sensor", DOMAIN, unique_id)
    assert entity_id is not None
    entity_registry.async_update_entity(entity_id, disabled_by=None)
    with patch("homeassistant.components.icloud.PLATFORMS", [Platform.BINARY_SENSOR]):
        await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("status", "unique_id", "expected"),
    [
        pytest.param({}, "device1_online", "on", id="online"),
        pytest.param(
            {"deviceStatus": "201"}, "device1_online", "off", id="online_offline"
        ),
        pytest.param(
            {"lowPowerMode": True},
            "device1_low_power_mode",
            "on",
            id="low_power_mode",
        ),
        pytest.param(
            {"activationLocked": True},
            "device1_activation_lock",
            "on",
            id="activation_lock",
        ),
        pytest.param(
            {"locationEnabled": False},
            "device1_location_services",
            "off",
            id="location_services_off",
        ),
        pytest.param(
            {"location": {**LOCATION, "isOld": True}},
            "device1_location_current",
            "on",
            id="location_current",
        ),
        pytest.param(
            {"location": {**LOCATION, "isInaccurate": True}},
            "device1_location_accurate",
            "on",
            id="location_accurate",
        ),
        pytest.param(
            {"wipeInProgress": True},
            "device1_wipe_in_progress",
            "on",
            id="wipe_in_progress",
        ),
        pytest.param(
            {"remoteLock": {"statusCode": "2201"}},
            "device1_remote_lock",
            "on",
            id="remote_lock_pending",
        ),
        pytest.param(
            {"remoteLock": {"statusCode": "200"}},
            "device1_remote_lock",
            "off",
            id="remote_lock_completed",
        ),
        pytest.param(
            {"lostModeCapable": True, "lostModeEnabled": True},
            "device1_lost_mode",
            "on",
            id="lost_mode",
        ),
        pytest.param(
            {"lostModeCapable": True, "lostModeEnabled": False},
            "device1_lost_mode",
            "off",
            id="lost_mode_off",
        ),
    ],
)
async def test_binary_sensor_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    icloud_service: MagicMock,
    setup_entry: Callable[[Platform], Awaitable[None]],
    status: dict,
    unique_id: str,
    expected: str,
) -> None:
    """Binary sensors reflect the device status."""
    icloud_service.devices.add({**DEVICE, **status})

    await setup_entry(Platform.BINARY_SENSOR)

    entity_id = entity_registry.async_get_entity_id("binary_sensor", DOMAIN, unique_id)
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected


async def test_binary_sensor_does_not_carry_device_attributes(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    icloud_service: MagicMock,
    setup_entry: Callable[[Platform], Awaitable[None]],
) -> None:
    """Binary sensors do not expose the attributes of the battery sensor."""
    icloud_service.devices.add(DEVICE)

    await setup_entry(Platform.BINARY_SENSOR)

    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, "device1_online"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert ATTR_DEVICE_STATUS not in state.attributes


async def test_locating_disabled_by_default(
    entity_registry: er.EntityRegistry,
    icloud_service: MagicMock,
    setup_entry: Callable[[Platform], Awaitable[None]],
) -> None:
    """The locating binary sensor is disabled by default."""
    icloud_service.devices.add(DEVICE)

    await setup_entry(Platform.BINARY_SENSOR)

    entry = entity_registry.async_get(
        entity_registry.async_get_entity_id("binary_sensor", DOMAIN, LOCATING_UNIQUE_ID)
    )
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_locating_state(
    hass: HomeAssistant,
    devices_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    icloud_service: MagicMock,
    setup_entry: Callable[[Platform], Awaitable[None]],
) -> None:
    """The locating binary sensor reports the flag once enabled."""
    icloud_service.devices.add({**DEVICE, "isLocating": True})

    await setup_entry(Platform.BINARY_SENSOR)
    await _async_enable_entity(
        hass, devices_config_entry, entity_registry, LOCATING_UNIQUE_ID
    )

    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, LOCATING_UNIQUE_ID
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"


@pytest.mark.parametrize(
    ("status", "unique_id"),
    [
        pytest.param(
            {"lostModeCapable": False},
            "device1_lost_mode",
            id="lost_mode_unsupported",
        ),
        pytest.param(
            {"features": {**FEATURES, "LCK": False}},
            "device1_activation_lock",
            id="activation_lock_unsupported",
        ),
        pytest.param(
            {"features": {**FEATURES, "LCK": False}},
            "device1_remote_lock",
            id="remote_lock_unsupported",
        ),
        pytest.param(
            {"features": {**FEATURES, "WIP": False}},
            "device1_wipe_in_progress",
            id="wipe_in_progress_unsupported",
        ),
        pytest.param(
            {"features": {**FEATURES, "LOC": False}, "location": LOCATION},
            "device1_location_current",
            id="location_current_unsupported",
        ),
        pytest.param(
            {"features": {**FEATURES, "LOC": False}, "location": LOCATION},
            "device1_location_accurate",
            id="location_accurate_unsupported",
        ),
    ],
)
async def test_binary_sensor_not_added_when_unsupported(
    entity_registry: er.EntityRegistry,
    icloud_service: MagicMock,
    setup_entry: Callable[[Platform], Awaitable[None]],
    status: dict,
    unique_id: str,
) -> None:
    """Binary sensors are only added for devices that support them."""
    icloud_service.devices.add({**DEVICE, **status})

    await setup_entry(Platform.BINARY_SENSOR)

    assert (
        entity_registry.async_get_entity_id("binary_sensor", DOMAIN, unique_id) is None
    )


async def test_location_binary_sensors_not_added_without_location(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    icloud_service: MagicMock,
    setup_entry: Callable[[Platform], Awaitable[None]],
) -> None:
    """Location derived binary sensors are not added without a location fix."""
    icloud_service.devices.add({**DEVICE, "location": None})

    await setup_entry(Platform.BINARY_SENSOR)

    assert (
        entity_registry.async_get_entity_id("binary_sensor", DOMAIN, "device1_online")
        is not None
    )
    for unique_id in LOCATION_UNIQUE_IDS:
        assert (
            entity_registry.async_get_entity_id("binary_sensor", DOMAIN, unique_id)
            is None
        )


async def test_location_binary_sensors_added_when_location_appears(
    hass: HomeAssistant,
    devices_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    icloud_service: MagicMock,
    setup_entry: Callable[[Platform], Awaitable[None]],
) -> None:
    """Location derived binary sensors are added once a location is reported."""
    apple_device = icloud_service.devices.add({**DEVICE, "location": None})

    await setup_entry(Platform.BINARY_SENSOR)

    for unique_id in LOCATION_UNIQUE_IDS:
        assert (
            entity_registry.async_get_entity_id("binary_sensor", DOMAIN, unique_id)
            is None
        )

    apple_device.status()["location"] = LOCATION
    await hass.async_add_executor_job(devices_config_entry.runtime_data.update_devices)
    await hass.async_block_till_done()

    for unique_id in LOCATION_UNIQUE_IDS:
        assert (
            entity_registry.async_get_entity_id("binary_sensor", DOMAIN, unique_id)
            is not None
        )


async def test_location_flags_follow_the_reported_fix(
    hass: HomeAssistant,
    devices_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    icloud_service: MagicMock,
    setup_entry: Callable[[Platform], Awaitable[None]],
) -> None:
    """Location flags describe the reported fix, not the one kept in storage."""
    apple_device = icloud_service.devices.add(
        {**DEVICE, "location": {**LOCATION, "isOld": True}}
    )

    await setup_entry(Platform.BINARY_SENSOR)

    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, "device1_location_current"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"

    # Apple stops reporting a fix, but the stored one lingers, so the flag it
    # carried must go out of state rather than be reported indefinitely.
    apple_device.status()["location"] = None
    await hass.async_add_executor_job(devices_config_entry.runtime_data.update_devices)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"


async def test_lost_mode_binary_sensor_tracks_state(
    hass: HomeAssistant,
    devices_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    icloud_service: MagicMock,
    setup_entry: Callable[[Platform], Awaitable[None]],
) -> None:
    """The lost mode state follows the device status."""
    apple_device = icloud_service.devices.add(
        {**DEVICE, "lostModeCapable": True, "lostModeEnabled": False}
    )

    await setup_entry(Platform.BINARY_SENSOR)

    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, "device1_lost_mode"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"

    apple_device.status()["lostModeEnabled"] = True
    await hass.async_add_executor_job(devices_config_entry.runtime_data.update_devices)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"
