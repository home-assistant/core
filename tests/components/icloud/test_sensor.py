"""Tests for the iCloud sensor platform."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from homeassistant.components.icloud.const import DOMAIN
from homeassistant.const import STATE_UNKNOWN, EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DEVICE, FEATURES, LOCATION, LOCATION_TIMESTAMP_MS

from tests.common import MockConfigEntry
from tests.typing import MagicMock

BATTERY_UNIQUE_ID = "device1_battery"
BATTERY_STATUS_UNIQUE_ID = "device1_battery_status"
DEVICE_STATUS_UNIQUE_ID = "device1_device_status"
OWNER_UNIQUE_ID = "device1_owner"
LOCATION_UNIQUE_ID = "device1_last_location"
LOCATION_ACCURACY_UNIQUE_ID = "device1_location_accuracy"
LOCATION_TYPE_UNIQUE_ID = "device1_location_type"
ALTITUDE_UNIQUE_ID = "device1_altitude"
FLOOR_LEVEL_UNIQUE_ID = "device1_floor_level"
LAST_LOCKED_UNIQUE_ID = "device1_last_locked"
LAST_LOST_UNIQUE_ID = "device1_last_lost"
LAST_WIPED_UNIQUE_ID = "device1_last_wiped"

LOCATION_UNIQUE_IDS = [
    LOCATION_UNIQUE_ID,
    LOCATION_ACCURACY_UNIQUE_ID,
    LOCATION_TYPE_UNIQUE_ID,
    ALTITUDE_UNIQUE_ID,
    FLOOR_LEVEL_UNIQUE_ID,
]

# Timestamp sensors only report something after the matching event happened, so
# an enabled by default sensor would sit at unknown for most devices.
DISABLED_UNIQUE_IDS = [
    LAST_LOCKED_UNIQUE_ID,
    LAST_LOST_UNIQUE_ID,
    LAST_WIPED_UNIQUE_ID,
]

LOCATION_TIMESTAMP = datetime.fromtimestamp(LOCATION_TIMESTAMP_MS / 1000, tz=UTC)

DIAGNOSTIC_UNIQUE_IDS = [
    BATTERY_STATUS_UNIQUE_ID,
    DEVICE_STATUS_UNIQUE_ID,
    OWNER_UNIQUE_ID,
    LOCATION_UNIQUE_ID,
    LOCATION_ACCURACY_UNIQUE_ID,
    LOCATION_TYPE_UNIQUE_ID,
    ALTITUDE_UNIQUE_ID,
    FLOOR_LEVEL_UNIQUE_ID,
]


async def _async_enable_entity(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    unique_id: str,
) -> None:
    """Enable a disabled by default sensor and reload the entry."""
    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id is not None
    entity_registry.async_update_entity(entity_id, disabled_by=None)
    with patch("homeassistant.components.icloud.PLATFORMS", [Platform.SENSOR]):
        await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("status", "unique_id", "expected"),
    [
        pytest.param({}, BATTERY_STATUS_UNIQUE_ID, "not_charging", id="battery_status"),
        pytest.param(
            {"batteryStatus": "Charging"},
            BATTERY_STATUS_UNIQUE_ID,
            "charging",
            id="battery_status_charging",
        ),
        pytest.param({}, DEVICE_STATUS_UNIQUE_ID, "online", id="device_status"),
        pytest.param(
            {"deviceStatus": "201"},
            DEVICE_STATUS_UNIQUE_ID,
            "offline",
            id="device_status_offline",
        ),
        pytest.param({}, OWNER_UNIQUE_ID, "user name", id="owner"),
        pytest.param(
            {"location": LOCATION},
            LOCATION_TYPE_UNIQUE_ID,
            "gps",
            id="location_type",
        ),
        pytest.param(
            {"location": LOCATION},
            LOCATION_UNIQUE_ID,
            LOCATION_TIMESTAMP.isoformat(timespec="seconds"),
            id="last_location",
        ),
    ],
)
async def test_sensor_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    icloud_service: MagicMock,
    setup_entry: Callable[[Platform], Awaitable[None]],
    status: dict,
    unique_id: str,
    expected: str,
) -> None:
    """Sensors reflect the device status."""
    icloud_service.devices.add({**DEVICE, **status})

    await setup_entry(Platform.SENSOR)

    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected


@pytest.mark.parametrize("unique_id", DISABLED_UNIQUE_IDS)
async def test_timestamp_sensors_disabled_by_default(
    entity_registry: er.EntityRegistry,
    icloud_service: MagicMock,
    setup_entry: Callable[[Platform], Awaitable[None]],
    unique_id: str,
) -> None:
    """Timestamp sensors are disabled by default."""
    icloud_service.devices.add(DEVICE)

    await setup_entry(Platform.SENSOR)

    entry = entity_registry.async_get(
        entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    )
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.parametrize(
    ("status", "unique_id", "expected"),
    [
        pytest.param({}, LAST_LOCKED_UNIQUE_ID, STATE_UNKNOWN, id="last_locked_unset"),
        pytest.param(
            {"lockedTimestamp": LOCATION_TIMESTAMP_MS},
            LAST_LOCKED_UNIQUE_ID,
            LOCATION_TIMESTAMP.isoformat(timespec="seconds"),
            id="last_locked",
        ),
        pytest.param(
            {"lostTimestamp": "2024-01-15T10:30:00+00:00"},
            LAST_LOST_UNIQUE_ID,
            datetime(2024, 1, 15, 10, 30, tzinfo=UTC).isoformat(timespec="seconds"),
            id="last_lost",
        ),
        pytest.param(
            {"wipedTimestamp": LOCATION_TIMESTAMP_MS},
            LAST_WIPED_UNIQUE_ID,
            LOCATION_TIMESTAMP.isoformat(timespec="seconds"),
            id="last_wiped",
        ),
    ],
)
async def test_timestamp_sensor_state(
    hass: HomeAssistant,
    devices_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    icloud_service: MagicMock,
    setup_entry: Callable[[Platform], Awaitable[None]],
    status: dict,
    unique_id: str,
    expected: str,
) -> None:
    """Timestamp sensors report the device timestamps once enabled."""
    icloud_service.devices.add({**DEVICE, **status})

    await setup_entry(Platform.SENSOR)
    await _async_enable_entity(hass, devices_config_entry, entity_registry, unique_id)

    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected


@pytest.mark.parametrize(
    ("status", "unique_id"),
    [
        pytest.param(
            {"features": {**FEATURES, "LCK": False}},
            LAST_LOCKED_UNIQUE_ID,
            id="last_locked_unsupported",
        ),
        pytest.param(
            {"lostModeCapable": False},
            LAST_LOST_UNIQUE_ID,
            id="last_lost_unsupported",
        ),
        pytest.param(
            {"features": {**FEATURES, "WIP": False}},
            LAST_WIPED_UNIQUE_ID,
            id="last_wiped_unsupported",
        ),
        pytest.param(
            {"features": {**FEATURES, "LOC": False}, "location": LOCATION},
            LOCATION_UNIQUE_ID,
            id="last_location_unsupported",
        ),
        pytest.param(
            {"features": {**FEATURES, "LOC": False}, "location": LOCATION},
            LOCATION_ACCURACY_UNIQUE_ID,
            id="location_accuracy_unsupported",
        ),
    ],
)
async def test_sensor_not_added_when_unsupported(
    entity_registry: er.EntityRegistry,
    icloud_service: MagicMock,
    setup_entry: Callable[[Platform], Awaitable[None]],
    status: dict,
    unique_id: str,
) -> None:
    """Sensors are only added for devices that support them."""
    icloud_service.devices.add({**DEVICE, **status})

    await setup_entry(Platform.SENSOR)

    assert entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id) is None


@pytest.mark.parametrize(
    ("status", "unique_id", "expected"),
    [
        pytest.param({}, BATTERY_UNIQUE_ID, 80, id="battery"),
        pytest.param(
            {"location": LOCATION},
            LOCATION_ACCURACY_UNIQUE_ID,
            10,
            id="location_accuracy",
        ),
        pytest.param({"location": LOCATION}, ALTITUDE_UNIQUE_ID, 5, id="altitude"),
        pytest.param(
            {"location": LOCATION}, FLOOR_LEVEL_UNIQUE_ID, 2, id="floor_level"
        ),
    ],
)
async def test_numeric_sensor_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    icloud_service: MagicMock,
    setup_entry: Callable[[Platform], Awaitable[None]],
    status: dict,
    unique_id: str,
    expected: float,
) -> None:
    """Numeric sensors expose their device value."""
    icloud_service.devices.add({**DEVICE, **status})

    await setup_entry(Platform.SENSOR)

    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == expected


async def test_new_sensors_are_diagnostic(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    icloud_service: MagicMock,
    setup_entry: Callable[[Platform], Awaitable[None]],
) -> None:
    """The added sensors are diagnostic, except the battery level."""
    icloud_service.devices.add({**DEVICE, "location": LOCATION})

    await setup_entry(Platform.SENSOR)

    battery_entry = entity_registry.async_get(
        entity_registry.async_get_entity_id("sensor", DOMAIN, BATTERY_UNIQUE_ID)
    )
    assert battery_entry is not None
    assert battery_entry.entity_category is None

    for unique_id in DIAGNOSTIC_UNIQUE_IDS:
        entry = entity_registry.async_get(
            entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        )
        assert entry is not None
        assert entry.entity_category is EntityCategory.DIAGNOSTIC


async def test_location_sensors_not_added_without_location(
    entity_registry: er.EntityRegistry,
    icloud_service: MagicMock,
    setup_entry: Callable[[Platform], Awaitable[None]],
) -> None:
    """Location derived sensors are not added without a location fix."""
    icloud_service.devices.add({**DEVICE, "location": None})

    await setup_entry(Platform.SENSOR)

    for unique_id in LOCATION_UNIQUE_IDS:
        assert entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id) is None

    for unique_id in (BATTERY_UNIQUE_ID, BATTERY_STATUS_UNIQUE_ID, OWNER_UNIQUE_ID):
        assert (
            entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id) is not None
        )


async def test_location_sensors_added_when_location_appears(
    hass: HomeAssistant,
    devices_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    icloud_service: MagicMock,
    setup_entry: Callable[[Platform], Awaitable[None]],
) -> None:
    """Location derived sensors are added once the device reports a location."""
    apple_device = icloud_service.devices.add({**DEVICE, "location": None})

    await setup_entry(Platform.SENSOR)

    for unique_id in LOCATION_UNIQUE_IDS:
        assert entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id) is None

    apple_device.status()["location"] = LOCATION
    await hass.async_add_executor_job(devices_config_entry.runtime_data.update_devices)
    await hass.async_block_till_done()

    for unique_id in LOCATION_UNIQUE_IDS:
        assert (
            entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id) is not None
        )


async def test_last_location_sensor_without_timestamp(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    icloud_service: MagicMock,
    setup_entry: Callable[[Platform], Awaitable[None]],
) -> None:
    """A location fix without a timestamp reports an unknown location time."""
    icloud_service.devices.add(
        {
            **DEVICE,
            "location": {
                "latitude": 1.0,
                "longitude": 2.0,
                "horizontalAccuracy": 10,
            },
        }
    )

    await setup_entry(Platform.SENSOR)

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, LOCATION_UNIQUE_ID
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN
