"""Tests for the LoJack device tracker platform."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

from freezegun import freeze_time
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.lojack.const import ATTR_LAST_POLLED
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import (
    TEST_ADDRESS,
    TEST_BATTERY_VOLTAGE,
    TEST_COLOR,
    TEST_DEVICE_ID,
    TEST_ENGINE_HOURS,
    TEST_HEADING,
    TEST_LATITUDE,
    TEST_LICENSE_PLATE,
    TEST_LONGITUDE,
    TEST_MAKE,
    TEST_MODEL,
    TEST_ODOMETER,
    TEST_SPEED,
    TEST_TIMESTAMP,
    TEST_VIN,
    TEST_YEAR,
)

from tests.common import MockConfigEntry, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all device tracker entities are created."""
    with patch("homeassistant.components.lojack.PLATFORMS", [Platform.DEVICE_TRACKER]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_device_tracker_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
) -> None:
    """Test device tracker state and attributes."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("device_tracker.2021_honda_accord")
    assert state is not None
    assert state.state == "not_home"

    # Check location attributes
    attrs = state.attributes
    assert attrs["latitude"] == TEST_LATITUDE
    assert attrs["longitude"] == TEST_LONGITUDE
    assert attrs["gps_accuracy"] == 10
    assert attrs["source_type"] == SourceType.GPS

    # Check extra state attributes
    assert attrs["vin"] == TEST_VIN
    assert attrs["make"] == TEST_MAKE
    assert attrs["model"] == TEST_MODEL
    assert attrs["year"] == TEST_YEAR
    assert attrs["color"] == TEST_COLOR
    assert attrs["license_plate"] == TEST_LICENSE_PLATE
    assert attrs["odometer"] == TEST_ODOMETER
    assert attrs["speed"] == TEST_SPEED
    assert attrs["heading"] == TEST_HEADING
    assert attrs["battery_voltage"] == TEST_BATTERY_VOLTAGE
    assert attrs["engine_hours"] == TEST_ENGINE_HOURS
    assert attrs["address"] == TEST_ADDRESS
    assert attrs["timestamp"] == TEST_TIMESTAMP


async def test_device_tracker_without_location(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: AsyncMock,
) -> None:
    """Test device tracker when location is unavailable."""
    mock_device.get_location = AsyncMock(side_effect=Exception("No location"))

    client = AsyncMock()
    client.list_devices = AsyncMock(return_value=[mock_device])
    client.close = AsyncMock()

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.LoJackClient.create",
            return_value=client,
        ),
    ):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get("device_tracker.my_car")
    assert state is not None


async def test_device_tracker_unique_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that device tracker has correct unique ID."""
    await setup_integration(hass, mock_config_entry)

    entity_entry = entity_registry.async_get("device_tracker.2021_honda_accord")
    assert entity_entry is not None
    assert entity_entry.unique_id == TEST_DEVICE_ID


@freeze_time("2024-01-15T12:00:00+00:00")
async def test_device_tracker_last_polled_attribute(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
) -> None:
    """Test that device tracker includes last_polled attribute.

    The last_polled attribute tracks when Home Assistant last fetched data
    from the LoJack API, which can differ from the device's timestamp
    (when the device last reported its location to LoJack servers).
    """
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("device_tracker.2021_honda_accord")
    assert state is not None

    # Check that last_polled attribute is present and is a datetime
    attrs = state.attributes
    assert ATTR_LAST_POLLED in attrs
    last_polled = attrs[ATTR_LAST_POLLED]
    assert isinstance(last_polled, datetime)

    # The last_polled should be around the frozen time
    assert last_polled.year == 2024
    assert last_polled.month == 1
    assert last_polled.day == 15
