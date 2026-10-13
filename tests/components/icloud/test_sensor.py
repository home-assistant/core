"""Tests for the iCloud sensor platform."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import pytest

from homeassistant.components.icloud.const import DOMAIN
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DEVICE, LOCATION, LOCATION_TIMESTAMP_MS

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
        pytest.param({}, "device1_last_locked", "unknown", id="last_locked_unset"),
        pytest.param(
            {"lockedTimestamp": LOCATION_TIMESTAMP_MS},
            "device1_last_locked",
            LOCATION_TIMESTAMP.isoformat(timespec="seconds"),
            id="last_locked",
        ),
        pytest.param(
            {"lostTimestamp": "2024-01-15T10:30:00+00:00"},
            "device1_last_lost",
            datetime(2024, 1, 15, 10, 30, tzinfo=UTC).isoformat(timespec="seconds"),
            id="last_lost",
        ),
        pytest.param(
            {"wipedTimestamp": LOCATION_TIMESTAMP_MS},
            "device1_last_wiped",
            LOCATION_TIMESTAMP.isoformat(timespec="seconds"),
            id="last_wiped",
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
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    icloud_service: MagicMock,
    setup_entry: Callable[[Platform], Awaitable[None]],
) -> None:
    """Location derived sensors are not added without a location fix."""
    icloud_service.devices.add({**DEVICE, "location": None})

    await setup_entry(Platform.SENSOR)

    for unique_id in (
        LOCATION_UNIQUE_ID,
        LOCATION_ACCURACY_UNIQUE_ID,
        LOCATION_TYPE_UNIQUE_ID,
        ALTITUDE_UNIQUE_ID,
        FLOOR_LEVEL_UNIQUE_ID,
    ):
        assert entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id) is None

    for unique_id in (BATTERY_UNIQUE_ID, BATTERY_STATUS_UNIQUE_ID, OWNER_UNIQUE_ID):
        assert (
            entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id) is not None
        )


async def test_location_sensor_not_added_without_timestamp(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    icloud_service: MagicMock,
    setup_entry: Callable[[Platform], Awaitable[None]],
) -> None:
    """No location fix sensor is added when the fix has no timestamp."""
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

    assert (
        entity_registry.async_get_entity_id("sensor", DOMAIN, BATTERY_UNIQUE_ID)
        is not None
    )
    assert (
        entity_registry.async_get_entity_id("sensor", DOMAIN, LOCATION_UNIQUE_ID)
        is None
    )
