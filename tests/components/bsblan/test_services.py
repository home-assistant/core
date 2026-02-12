"""Tests for BSB-LAN services."""

from datetime import time
from typing import Any
from unittest.mock import MagicMock

from bsblan import BSBLANError, DaySchedule, DeviceTime, TimeSlot
from freezegun.api import FrozenDateTimeFactory
import pytest
import voluptuous as vol

from homeassistant.components.bsblan.const import DOMAIN
from homeassistant.components.bsblan.services import (
    SERVICE_SET_HOT_WATER_SCHEDULE,
    async_setup_services,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry

# Test constants
TEST_DEVICE_MAC = "00:80:41:19:69:90"


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
) -> None:
    """Set up the BSB-LAN integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture
def device_entry(
    device_registry: dr.DeviceRegistry,
    setup_integration: None,
) -> dr.DeviceEntry:
    """Get the device entry for testing."""
    device = device_registry.async_get_device(identifiers={(DOMAIN, TEST_DEVICE_MAC)})
    assert device is not None
    return device


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize(
    ("service_data", "expected_schedules"),
    [
        (
            {
                "monday_slots": [
                    {"start_time": time(6, 0), "end_time": time(8, 0)},
                    {"start_time": time(17, 0), "end_time": time(21, 0)},
                ],
                "tuesday_slots": [
                    {"start_time": time(6, 0), "end_time": time(8, 0)},
                ],
            },
            {
                "monday": DaySchedule(
                    slots=[
                        TimeSlot(start=time(6, 0), end=time(8, 0)),
                        TimeSlot(start=time(17, 0), end=time(21, 0)),
                    ]
                ),
                "tuesday": DaySchedule(
                    slots=[TimeSlot(start=time(6, 0), end=time(8, 0))]
                ),
            },
        ),
        (
            {
                "friday_slots": [
                    {"start_time": time(17, 0), "end_time": time(21, 0)},
                ],
                "saturday_slots": [
                    {"start_time": time(8, 0), "end_time": time(22, 0)},
                ],
            },
            {
                "friday": DaySchedule(
                    slots=[TimeSlot(start=time(17, 0), end=time(21, 0))]
                ),
                "saturday": DaySchedule(
                    slots=[TimeSlot(start=time(8, 0), end=time(22, 0))]
                ),
            },
        ),
        (
            {
                "wednesday_slots": [
                    {"start_time": time(6, 0), "end_time": time(8, 0)},
                ],
            },
            {
                "wednesday": DaySchedule(
                    slots=[TimeSlot(start=time(6, 0), end=time(8, 0))]
                ),
            },
        ),
        (
            {
                "monday_slots": [],  # Empty array (shouldn't happen in UI)
            },
            {
                "monday": DaySchedule(slots=[]),
            },
        ),
    ],
    ids=[
        "multiple_slots_per_day",
        "weekend_schedule",
        "single_day",
        "clear_schedule_with_empty_array",
    ],
)
async def test_set_hot_water_schedule(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    device_entry: dr.DeviceEntry,
    service_data: dict[str, Any],
    expected_schedules: dict[str, DaySchedule],
) -> None:
    """Test setting hot water schedule with various configurations."""
    # Call the service with device_id and slot fields
    service_call_data = {"device_id": device_entry.id}
    service_call_data.update(service_data)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HOT_WATER_SCHEDULE,
        service_call_data,
        blocking=True,
    )

    # Verify the service was called correctly
    assert len(mock_bsblan.set_hot_water_schedule.mock_calls) == 1
    call_args = mock_bsblan.set_hot_water_schedule.call_args

    # Verify expected values - all values are in the DHWSchedule object
    dhw_schedule = call_args.args[0]
    for key, expected_schedule in expected_schedules.items():
        actual_schedule = getattr(dhw_schedule, key)
        assert actual_schedule == expected_schedule


async def test_invalid_device_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
) -> None:
    """Test error when device ID is invalid."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_HOT_WATER_SCHEDULE,
            {
                "device_id": "invalid_device_id",
                "monday_slots": [
                    {"start_time": time(6, 0), "end_time": time(8, 0)},
                ],
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "invalid_device_id"


@pytest.mark.parametrize(
    ("service_name", "service_data"),
    [
        (
            SERVICE_SET_HOT_WATER_SCHEDULE,
            {"monday_slots": [{"start_time": time(6, 0), "end_time": time(8, 0)}]},
        ),
        ("sync_time", {}),
    ],
    ids=["set_hot_water_schedule", "sync_time"],
)
async def test_no_config_entry_for_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    service_name: str,
    service_data: dict[str, Any],
) -> None:
    """Test error when device has no matching BSB-LAN config entry."""
    # Create a different config entry (not for bsblan)
    other_entry = MockConfigEntry(domain="other_domain", data={})
    other_entry.add_to_hass(hass)

    # Create a device for that other entry
    device_entry = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={("other_domain", "other_device")},
        name="Other Device",
    )

    # Register the bsblan service without setting up any bsblan config entry
    async_setup_services(hass)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            service_name,
            {"device_id": device_entry.id, **service_data},
            blocking=True,
        )

    assert exc_info.value.translation_key == "no_config_entry_for_device"


async def test_config_entry_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test error when config entry is not loaded."""
    # Add the config entry but don't set it up (so it stays in NOT_LOADED state)
    mock_config_entry.add_to_hass(hass)

    # Create the device manually since setup won't run
    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, TEST_DEVICE_MAC)},
        name="BSB-LAN Device",
    )

    # Register the service
    async_setup_services(hass)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_HOT_WATER_SCHEDULE,
            {
                "device_id": device_entry.id,
                "monday_slots": [
                    {"start_time": time(6, 0), "end_time": time(8, 0)},
                ],
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "config_entry_not_loaded"


@pytest.mark.usefixtures("setup_integration")
async def test_api_error(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    device_entry: dr.DeviceEntry,
) -> None:
    """Test error when BSB-LAN API call fails."""
    mock_bsblan.set_hot_water_schedule.side_effect = BSBLANError("API Error")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_HOT_WATER_SCHEDULE,
            {
                "device_id": device_entry.id,
                "monday_slots": [
                    {"start_time": time(6, 0), "end_time": time(8, 0)},
                ],
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "set_schedule_failed"


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize(
    ("start_time", "end_time", "expected_error"),
    [
        (time(13, 0), time(11, 0), "end_time_before_start_time"),
        ("13:00", "11:00", "end_time_before_start_time"),
    ],
    ids=[
        "time_objects_end_before_start",
        "strings_end_before_start",
    ],
)
async def test_time_validation_errors(
    hass: HomeAssistant,
    device_entry: dr.DeviceEntry,
    start_time: time | str,
    end_time: time | str,
    expected_error: str,
) -> None:
    """Test validation errors for various time input scenarios."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_HOT_WATER_SCHEDULE,
            {
                "device_id": device_entry.id,
                "monday_slots": [
                    {"start_time": start_time, "end_time": end_time},
                ],
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == expected_error


@pytest.mark.usefixtures("setup_integration")
async def test_unprovided_days_are_none(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    device_entry: dr.DeviceEntry,
) -> None:
    """Test that unprovided days are sent as None to BSB-LAN API."""
    # Only provide Monday and Tuesday, leave other days unprovided
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HOT_WATER_SCHEDULE,
        {
            "device_id": device_entry.id,
            "monday_slots": [
                {"start_time": time(6, 0), "end_time": time(8, 0)},
            ],
            "tuesday_slots": [
                {"start_time": time(17, 0), "end_time": time(21, 0)},
            ],
        },
        blocking=True,
    )

    # Verify the API was called
    assert mock_bsblan.set_hot_water_schedule.called
    call_args = mock_bsblan.set_hot_water_schedule.call_args
    dhw_schedule = call_args.args[0]

    # Verify provided days have values
    assert dhw_schedule.monday == DaySchedule(
        slots=[TimeSlot(start=time(6, 0), end=time(8, 0))]
    )
    assert dhw_schedule.tuesday == DaySchedule(
        slots=[TimeSlot(start=time(17, 0), end=time(21, 0))]
    )

    # Verify unprovided days are None (not empty DaySchedule)
    assert dhw_schedule.wednesday is None
    assert dhw_schedule.thursday is None
    assert dhw_schedule.friday is None
    assert dhw_schedule.saturday is None
    assert dhw_schedule.sunday is None


@pytest.mark.usefixtures("setup_integration")
async def test_string_time_formats(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    device_entry: dr.DeviceEntry,
) -> None:
    """Test service with string time formats."""
    # Test with string time formats
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HOT_WATER_SCHEDULE,
        {
            "device_id": device_entry.id,
            "monday_slots": [
                {"start_time": "06:00:00", "end_time": "08:00:00"},  # With seconds
            ],
            "tuesday_slots": [
                {"start_time": "17:00", "end_time": "21:00"},  # Without seconds
            ],
        },
        blocking=True,
    )

    # Verify the API was called
    assert mock_bsblan.set_hot_water_schedule.called
    call_args = mock_bsblan.set_hot_water_schedule.call_args
    dhw_schedule = call_args.args[0]

    # Should parse both formats correctly (seconds are stripped)
    assert dhw_schedule.monday == DaySchedule(
        slots=[TimeSlot(start=time(6, 0), end=time(8, 0))]
    )
    assert dhw_schedule.tuesday == DaySchedule(
        slots=[TimeSlot(start=time(17, 0), end=time(21, 0))]
    )


@pytest.mark.usefixtures("setup_integration")
async def test_non_standard_time_types(
    hass: HomeAssistant,
    device_entry: dr.DeviceEntry,
) -> None:
    """Test service with non-standard time types raises error."""
    # Test with integer time values - schema validation will reject these
    with pytest.raises(vol.MultipleInvalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_HOT_WATER_SCHEDULE,
            {
                "device_id": device_entry.id,
                "monday_slots": [
                    {"start_time": 600, "end_time": 800},
                ],
            },
            blocking=True,
        )


async def test_async_setup_services(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
) -> None:
    """Test service registration."""
    # Verify service doesn't exist initially
    assert not hass.services.has_service(DOMAIN, SERVICE_SET_HOT_WATER_SCHEDULE)

    # Set up the integration
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify service is now registered
    assert hass.services.has_service(DOMAIN, SERVICE_SET_HOT_WATER_SCHEDULE)


async def test_sync_time_service(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the sync_time service."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Get the device
    device = device_registry.async_get_device(identifiers={(DOMAIN, TEST_DEVICE_MAC)})
    assert device is not None

    # Mock device time that differs from HA time
    mock_bsblan.time.return_value = DeviceTime.from_json(
        '{"time": {"name": "Time", "value": "01.01.2020 00:00:00", "unit": "", "desc": "", "dataType": 0, "readonly": 0, "error": 0}}'
    )

    # Call the service
    await hass.services.async_call(
        DOMAIN,
        "sync_time",
        {"device_id": device.id},
        blocking=True,
    )

    # Verify time() was called to check current device time
    assert mock_bsblan.time.called

    # Verify set_time() was called with current HA time
    current_time_str = dt_util.now().strftime("%d.%m.%Y %H:%M:%S")
    mock_bsblan.set_time.assert_called_once_with(current_time_str)


async def test_sync_time_service_no_update_when_same(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the sync_time service doesn't update when time matches."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Get the device
    device = device_registry.async_get_device(identifiers={(DOMAIN, TEST_DEVICE_MAC)})
    assert device is not None

    # Mock device time that matches HA time
    current_time_str = dt_util.now().strftime("%d.%m.%Y %H:%M:%S")
    mock_bsblan.time.return_value = DeviceTime.from_json(
        f'{{"time": {{"name": "Time", "value": "{current_time_str}", "unit": "", "desc": "", "dataType": 0, "readonly": 0, "error": 0}}}}'
    )

    # Call the service
    await hass.services.async_call(
        DOMAIN,
        "sync_time",
        {"device_id": device.id},
        blocking=True,
    )

    # Verify time() was called
    assert mock_bsblan.time.called

    # Verify set_time() was NOT called since times match
    assert not mock_bsblan.set_time.called


async def test_sync_time_service_error_handling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the sync_time service handles errors gracefully."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Get the device
    device = device_registry.async_get_device(identifiers={(DOMAIN, TEST_DEVICE_MAC)})
    assert device is not None

    # Mock time() to raise an error
    mock_bsblan.time.side_effect = BSBLANError("Connection failed")

    # Call the service - should raise HomeAssistantError
    with pytest.raises(HomeAssistantError, match="Failed to sync time"):
        await hass.services.async_call(
            DOMAIN,
            "sync_time",
            {"device_id": device.id},
            blocking=True,
        )


async def test_sync_time_service_set_time_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the sync_time service handles set_time errors."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Get the device
    device = device_registry.async_get_device(identifiers={(DOMAIN, TEST_DEVICE_MAC)})
    assert device is not None

    # Mock device time that differs
    mock_bsblan.time.return_value = DeviceTime.from_json(
        '{"time": {"name": "Time", "value": "01.01.2020 00:00:00", "unit": "", "desc": "", "dataType": 0, "readonly": 0, "error": 0}}'
    )

    # Mock set_time() to raise an error
    mock_bsblan.set_time.side_effect = BSBLANError("Write failed")

    # Call the service - should raise HomeAssistantError
    with pytest.raises(HomeAssistantError, match="Failed to sync time"):
        await hass.services.async_call(
            DOMAIN,
            "sync_time",
            {"device_id": device.id},
            blocking=True,
        )


async def test_sync_time_service_entry_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
) -> None:
    """Test the sync_time service raises error for non-existent device."""
    # Set up the entry (this registers the service)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Call the service with a non-existent device ID
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "sync_time",
            {"device_id": "non_existent_device_id"},
            blocking=True,
        )


async def test_sync_time_service_entry_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the sync_time service raises error for unloaded entry."""
    # Set up the first entry (this registers the service)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Create a second unloaded entry
    unloaded_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Unloaded BSBLAN",
        data=mock_config_entry.data.copy(),
        unique_id="unloaded_unique_id",
    )
    unloaded_entry.add_to_hass(hass)
    # Don't call async_setup on this entry, so it stays NOT_LOADED

    # Manually register a device for this unloaded entry
    unloaded_device = device_registry.async_get_or_create(
        config_entry_id=unloaded_entry.entry_id,
        identifiers={(DOMAIN, "unloaded_device_mac")},
        name="Unloaded Device",
    )

    # Call the service with the device from the unloaded entry - should raise error
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "sync_time",
            {"device_id": unloaded_device.id},
            blocking=True,
        )
