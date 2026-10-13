"""Tests for the iCloud binary sensor platform."""

from collections.abc import Awaitable, Callable

import pytest

from homeassistant.components.icloud.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DEVICE, FEATURES, LOCATION

from tests.common import MockConfigEntry
from tests.typing import MagicMock

LOCATION_UNIQUE_IDS = ["device1_location_is_old", "device1_location_is_inaccurate"]


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
        pytest.param({"isLocating": True}, "device1_locating", "on", id="locating"),
        pytest.param(
            {"locationEnabled": False},
            "device1_location_services",
            "off",
            id="location_services_off",
        ),
        pytest.param(
            {"location": {**LOCATION, "isOld": True}},
            "device1_location_is_old",
            "on",
            id="location_is_old",
        ),
        pytest.param(
            {"location": {**LOCATION, "isInaccurate": True}},
            "device1_location_is_inaccurate",
            "on",
            id="location_is_inaccurate",
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
            "device1_location_is_old",
            id="location_is_old_unsupported",
        ),
        pytest.param(
            {"features": {**FEATURES, "LOC": False}, "location": LOCATION},
            "device1_location_is_inaccurate",
            id="location_is_inaccurate_unsupported",
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
    icloud_service.devices.add(DEVICE)

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
