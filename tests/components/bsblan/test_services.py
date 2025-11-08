"""Tests for BSB-LAN services."""

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
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("schedule_data", "expected_calls"),
    [
        (
            {
                "monday": "06:00-08:00 17:00-21:00",
                "tuesday": "06:00-08:00 17:00-21:00",
                "wednesday": "06:00-08:00 17:00-21:00",
                "thursday": "06:00-08:00 17:00-21:00",
                "friday": "06:00-08:00 17:00-21:00",
                "saturday": "08:00-22:00",
                "sunday": "08:00-22:00",
            },
            {
                "monday": "06:00-08:00 17:00-21:00",
                "tuesday": "06:00-08:00 17:00-21:00",
                "saturday": "08:00-22:00",
            },
        ),
        (
            {
                "monday": "06:00-08:00",
                "friday": "17:00-21:00",
            },
            {
                "monday": "06:00-08:00",
                "friday": "17:00-21:00",
            },
        ),
        (
            {
                "monday": None,
                "tuesday": None,
            },
            {
                "monday": None,
                "tuesday": None,
            },
        ),
        (
            {
                "wednesday": "06:00-08:00",
                "standard_values": True,
            },
            {
                "wednesday": "06:00-08:00",
                "standard_values": "True",  # Converted to string by service layer
            },
        ),
    ],
    ids=[
        "full_week_schedule",
        "partial_days",
        "clear_days_with_none",
        "with_standard_values",
    ],
)
async def test_service_set_hot_water_schedule(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
    schedule_data: dict[str, Any],
    expected_calls: dict[str, Any],
) -> None:
    """Test setting hot water schedule with various configurations."""
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
            "schedule": schedule_data,
        },
        blocking=True,
    )

    # Verify the service was called correctly
    assert len(mock_bsblan.set_hot_water.mock_calls) == 1
    call_args = mock_bsblan.set_hot_water.call_args

    # Verify expected values - all values are in the dhw_time_programs object
    dhw_programs = call_args.kwargs["dhw_time_programs"]
    for key, value in expected_calls.items():
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
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_HOT_WATER_SCHEDULE,
            {
                "device": device_id,
                "schedule": {"monday": "06:00-08:00"},
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == expected_translation_key

    assert exc_info.value.translation_key == expected_translation_key


async def test_async_setup_services(hass: HomeAssistant) -> None:
    """Test service registration."""
    # Verify service doesn't exist initially
    assert not hass.services.has_service(DOMAIN, SERVICE_SET_HOT_WATER_SCHEDULE)

    # Register services
    async_setup_services(hass)

    # Verify service is now registered
    assert hass.services.has_service(DOMAIN, SERVICE_SET_HOT_WATER_SCHEDULE)


async def test_async_unload_services_when_last_entry_removed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
) -> None:
    """Test services are removed when the last config entry is unloaded."""
    # Setup the config entry
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify service is registered
    assert hass.services.has_service(DOMAIN, SERVICE_SET_HOT_WATER_SCHEDULE)

    # Unload the config entry
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify service is removed when last entry is unloaded
    assert not hass.services.has_service(DOMAIN, SERVICE_SET_HOT_WATER_SCHEDULE)
