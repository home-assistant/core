"""Tests for BSB-LAN services."""

from datetime import time
from typing import Any
from unittest.mock import MagicMock

from bsblan import BSBLANError
import pytest

from homeassistant.components.bsblan.const import DOMAIN
from homeassistant.components.bsblan.services import (
    SERVICE_SET_HOT_WATER_SCHEDULE,
    async_setup_services,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("service_data", "expected_strings"),
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
                "monday": "06:00-08:00 17:00-21:00",
                "tuesday": "06:00-08:00",
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
                "friday": "17:00-21:00",
                "saturday": "08:00-22:00",
            },
        ),
        (
            {
                "wednesday_slots": [
                    {"start_time": time(6, 0), "end_time": time(8, 0)},
                ],
            },
            {
                "wednesday": "06:00-08:00",
            },
        ),
        (
            {
                "standard_values_slots": [
                    {"start_time": time(7, 0), "end_time": time(20, 0)},
                ],
            },
            {
                "standard_values": "07:00-20:00",
            },
        ),
        (
            {
                "monday_slots": [],  # Empty array (shouldn't happen in UI)
            },
            {
                "monday": "",
            },
        ),
    ],
    ids=[
        "multiple_slots_per_day",
        "weekend_schedule",
        "single_day",
        "standard_values",
        "clear_schedule_with_empty_array",
    ],
)
async def test_set_hot_water_schedule(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    service_data: dict[str, Any],
    expected_strings: dict[str, str],
) -> None:
    """Test setting hot water schedule with various configurations."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Get the device ID
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "00:80:41:19:69:90")}
    )
    assert device_entry is not None

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
    assert len(mock_bsblan.set_hot_water.mock_calls) == 1
    call_args = mock_bsblan.set_hot_water.call_args

    # Verify expected values - all values are in the dhw_time_programs object
    dhw_programs = call_args.kwargs["dhw_time_programs"]
    for key, value in expected_strings.items():
        assert getattr(dhw_programs, key) == value


@pytest.mark.parametrize(
    ("setup_error", "device_id_override", "expected_translation_key"),
    [
        (None, "invalid_device_id", "invalid_device_id"),
        ("no_config_entry", None, "no_config_entry_for_device"),
        ("config_entry_not_loaded", None, "config_entry_not_loaded"),
        ("api_error", None, "set_schedule_failed"),
    ],
    ids=[
        "invalid_device_id",
        "no_config_entry_for_device",
        "config_entry_not_loaded",
        "api_error",
    ],
)
async def test_service_error_scenarios(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
    setup_error: str | None,
    device_id_override: str | None,
    expected_translation_key: str,
) -> None:
    """Test service error scenarios."""
    if setup_error == "no_config_entry":
        # Create a different config entry (not for bsblan)
        other_entry = MockConfigEntry(domain="other_domain", data={})
        other_entry.add_to_hass(hass)

        # Create a device for that other entry
        device_registry = dr.async_get(hass)
        device_entry = device_registry.async_get_or_create(
            config_entry_id=other_entry.entry_id,
            identifiers={("other_domain", "other_device")},
            name="Other Device",
        )
        device_id = device_entry.id

        # Register the bsblan service without setting up any bsblan config entry
        async_setup_services(hass)
    elif setup_error == "config_entry_not_loaded":
        # Add the config entry but don't set it up (so it stays in NOT_LOADED state)
        mock_config_entry.add_to_hass(hass)

        # Create the device manually since setup won't run
        device_registry = dr.async_get(hass)
        device_entry = device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id,
            identifiers={(DOMAIN, "00:80:41:19:69:90")},
            name="BSB-LAN Device",
        )
        device_id = device_entry.id

        # Register the service
        async_setup_services(hass)
    else:
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        device_registry = dr.async_get(hass)
        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN, "00:80:41:19:69:90")}
        )
        assert device_entry is not None
        device_id = device_entry.id

        if setup_error == "api_error":
            # Make the API call fail
            mock_bsblan.set_hot_water.side_effect = BSBLANError("API Error")

    # Override device ID if needed
    if device_id_override:
        device_id = device_id_override

    # Call the service and expect error
    # API errors raise HomeAssistantError, user input errors raise ServiceValidationError
    expected_exception = (
        HomeAssistantError if setup_error == "api_error" else ServiceValidationError
    )
    with pytest.raises(expected_exception) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_HOT_WATER_SCHEDULE,
            {
                "device_id": device_id,
                "monday_slots": [
                    {"start_time": time(6, 0), "end_time": time(8, 0)},
                ],
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == expected_translation_key


async def test_end_time_before_start_time(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test validation error when end time is before start time."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "00:80:41:19:69:90")}
    )
    assert device_entry is not None

    # Try to create a time slot where end is before start
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_HOT_WATER_SCHEDULE,
            {
                "device_id": device_entry.id,
                "monday_slots": [
                    {"start_time": time(13, 0), "end_time": time(11, 0)},  # Invalid!
                ],
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "end_time_before_start_time"


async def test_string_time_formats(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test service with string time formats."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "00:80:41:19:69:90")}
    )
    assert device_entry is not None

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
    assert mock_bsblan.set_hot_water.called
    call_args = mock_bsblan.set_hot_water.call_args
    dhw_programs = call_args.kwargs["dhw_time_programs"]

    # Should strip seconds from both formats
    assert dhw_programs.monday == "06:00-08:00"
    assert dhw_programs.tuesday == "17:00-21:00"


async def test_invalid_time_format(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test service with invalid time format in string."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "00:80:41:19:69:90")}
    )
    assert device_entry is not None

    # Test with invalid start_time string format
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_HOT_WATER_SCHEDULE,
            {
                "device_id": device_entry.id,
                "monday_slots": [
                    {"start_time": "invalid", "end_time": "08:00"},
                ],
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "invalid_time_format"

    # Test with invalid end_time string format
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_HOT_WATER_SCHEDULE,
            {
                "device_id": device_entry.id,
                "tuesday_slots": [
                    {"start_time": "06:00", "end_time": "not-a-time"},
                ],
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "invalid_time_format"


async def test_string_time_validation(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that end time validation works with string times."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "00:80:41:19:69:90")}
    )
    assert device_entry is not None

    # Test with string format where end is before start
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_HOT_WATER_SCHEDULE,
            {
                "device_id": device_entry.id,
                "wednesday_slots": [
                    {"start_time": "13:00", "end_time": "11:00"},  # Invalid!
                ],
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "end_time_before_start_time"


async def test_non_standard_time_types(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test service with non-standard time types (edge case for coverage)."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "00:80:41:19:69:90")}
    )
    assert device_entry is not None

    # Test with integer time values (shouldn't happen but need coverage)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HOT_WATER_SCHEDULE,
        {
            "device_id": device_entry.id,
            "monday_slots": [
                {"start_time": 600, "end_time": 800},  # Non-standard types
            ],
        },
        blocking=True,
    )

    # Verify the API was called
    assert mock_bsblan.set_hot_water.called
    call_args = mock_bsblan.set_hot_water.call_args
    dhw_programs = call_args.kwargs["dhw_time_programs"]

    # Should convert to strings
    assert dhw_programs.monday == "600-800"


async def test_async_setup_services(hass: HomeAssistant) -> None:
    """Test service registration."""
    # Verify service doesn't exist initially
    assert not hass.services.has_service(DOMAIN, SERVICE_SET_HOT_WATER_SCHEDULE)

    # Register services
    async_setup_services(hass)

    # Verify service is now registered
    assert hass.services.has_service(DOMAIN, SERVICE_SET_HOT_WATER_SCHEDULE)
