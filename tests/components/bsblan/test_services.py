"""Tests for BSB-LAN services."""

from unittest.mock import MagicMock

from bsblan import BSBLANError
import pytest

from homeassistant.components.bsblan.const import DOMAIN
from homeassistant.components.bsblan.services import (
    SERVICE_SET_HOT_WATER_SCHEDULE,
    async_setup_services,
    async_unload_services,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_service_set_hot_water_schedule_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
) -> None:
    """Test successfully setting hot water schedule."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Get the device ID
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "00:80:41:19:69:90")}
    )
    assert device_entry is not None

    # Call the service
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HOT_WATER_SCHEDULE,
        {
            "device": device_entry.id,
            "schedule": {
                "monday": "06:00-08:00 17:00-21:00",
                "tuesday": "06:00-08:00 17:00-21:00",
                "wednesday": "06:00-08:00 17:00-21:00",
                "thursday": "06:00-08:00 17:00-21:00",
                "friday": "06:00-08:00 17:00-21:00",
                "saturday": "08:00-22:00",
                "sunday": "08:00-22:00",
            },
        },
        blocking=True,
    )

    # Verify the service was called correctly
    assert len(mock_bsblan.set_hot_water.mock_calls) == 1
    call_args = mock_bsblan.set_hot_water.call_args
    assert call_args.kwargs["dhw_time_programs"].monday == "06:00-08:00 17:00-21:00"
    assert call_args.kwargs["dhw_time_programs"].tuesday == "06:00-08:00 17:00-21:00"
    assert call_args.kwargs["dhw_time_programs"].saturday == "08:00-22:00"


async def test_service_set_hot_water_schedule_partial(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
) -> None:
    """Test setting hot water schedule with partial days."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "00:80:41:19:69:90")}
    )
    assert device_entry is not None

    # Call the service with only some days
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HOT_WATER_SCHEDULE,
        {
            "device": device_entry.id,
            "schedule": {
                "monday": "06:00-08:00",
                "friday": "17:00-21:00",
            },
        },
        blocking=True,
    )

    # Verify the service was called
    assert len(mock_bsblan.set_hot_water.mock_calls) == 1
    call_args = mock_bsblan.set_hot_water.call_args
    assert call_args.kwargs["dhw_time_programs"].monday == "06:00-08:00"
    assert call_args.kwargs["dhw_time_programs"].friday == "17:00-21:00"
    assert call_args.kwargs["dhw_time_programs"].tuesday is None


async def test_service_set_hot_water_schedule_with_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
) -> None:
    """Test setting hot water schedule with None values to clear days."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "00:80:41:19:69:90")}
    )
    assert device_entry is not None

    # Call the service with None values
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HOT_WATER_SCHEDULE,
        {
            "device": device_entry.id,
            "schedule": {
                "monday": None,
                "tuesday": "06:00-08:00",
            },
        },
        blocking=True,
    )

    # Verify the service was called
    assert len(mock_bsblan.set_hot_water.mock_calls) == 1
    call_args = mock_bsblan.set_hot_water.call_args
    assert call_args.kwargs["dhw_time_programs"].monday is None
    assert call_args.kwargs["dhw_time_programs"].tuesday == "06:00-08:00"


async def test_service_invalid_device_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
) -> None:
    """Test service call with invalid device ID."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Call the service with invalid device ID
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_HOT_WATER_SCHEDULE,
            {
                "device": "invalid_device_id",
                "schedule": {"monday": "06:00-08:00"},
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "invalid_device_id"
    assert "invalid_device_id" in exc_info.value.translation_placeholders["device_id"]


async def test_service_no_config_entry_for_device(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
) -> None:
    """Test service call when device has no associated config entry."""
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

    # Now register the bsblan service without setting up any bsblan config entry
    async_setup_services(hass)

    # Call the service with device from other domain
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_HOT_WATER_SCHEDULE,
            {
                "device": device_entry.id,
                "schedule": {"monday": "06:00-08:00"},
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "no_config_entry_for_device"


async def test_service_config_entry_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
) -> None:
    """Test service call when config entry is not loaded."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "00:80:41:19:69:90")}
    )
    assert device_entry is not None

    # Unload the config entry
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED

    # Call the service with unloaded config entry
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_HOT_WATER_SCHEDULE,
            {
                "device": device_entry.id,
                "schedule": {"monday": "06:00-08:00"},
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "config_entry_not_loaded"


async def test_service_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
) -> None:
    """Test service call when API raises an error."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "00:80:41:19:69:90")}
    )
    assert device_entry is not None

    # Make the API call fail
    mock_bsblan.set_hot_water.side_effect = BSBLANError("API Error")

    # Call the service
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_HOT_WATER_SCHEDULE,
            {
                "device": device_entry.id,
                "schedule": {"monday": "06:00-08:00"},
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "set_schedule_failed"
    assert "API Error" in exc_info.value.translation_placeholders["error"]


async def test_service_with_standard_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
) -> None:
    """Test setting hot water schedule with standard_values field."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "00:80:41:19:69:90")}
    )
    assert device_entry is not None

    # Call the service with standard_values
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HOT_WATER_SCHEDULE,
        {
            "device": device_entry.id,
            "schedule": {
                "standard_values": "06:00-08:00 17:00-21:00",
            },
        },
        blocking=True,
    )

    # Verify the service was called
    assert len(mock_bsblan.set_hot_water.mock_calls) == 1
    call_args = mock_bsblan.set_hot_water.call_args
    assert (
        call_args.kwargs["dhw_time_programs"].standard_values
        == "06:00-08:00 17:00-21:00"
    )


async def test_async_setup_services(hass: HomeAssistant) -> None:
    """Test service registration."""
    # Verify service doesn't exist initially
    assert not hass.services.has_service(DOMAIN, SERVICE_SET_HOT_WATER_SCHEDULE)

    # Register services
    async_setup_services(hass)

    # Verify service is now registered
    assert hass.services.has_service(DOMAIN, SERVICE_SET_HOT_WATER_SCHEDULE)


async def test_async_unload_services(hass: HomeAssistant) -> None:
    """Test service unregistration."""
    # Register services first
    async_setup_services(hass)
    assert hass.services.has_service(DOMAIN, SERVICE_SET_HOT_WATER_SCHEDULE)

    # Unload services
    async_unload_services(hass)

    # Verify service is removed
    assert not hass.services.has_service(DOMAIN, SERVICE_SET_HOT_WATER_SCHEDULE)
