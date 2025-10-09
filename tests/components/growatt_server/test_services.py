"""Test Growatt Server services."""

from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant.components.growatt_server.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


async def test_read_min_time_segments_single_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_growatt_api,
) -> None:
    """Test reading MIN time segments for single device."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.growatt_server.get_device_list"
    ) as mock_get_devices:
        mock_get_devices.return_value = (
            [{"deviceSn": "MIN123456", "deviceType": "min"}],
            "12345",
        )
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Test service call
    response = await hass.services.async_call(
        DOMAIN,
        "read_min_time_segments",
        {},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    assert "time_segments" in response
    assert len(response["time_segments"]) == 9  # Returns all 9 segments (1-9)


async def test_update_min_time_segment_charge_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_growatt_api,
) -> None:
    """Test updating MIN time segment with charge mode."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.growatt_server.get_device_list"
    ) as mock_get_devices:
        mock_get_devices.return_value = (
            [{"deviceSn": "MIN123456", "deviceType": "min"}],
            "12345",
        )
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Test successful update
    await hass.services.async_call(
        DOMAIN,
        "update_min_time_segment",
        {
            "segment_id": 1,
            "start_time": "09:00",
            "end_time": "11:00",
            "batt_mode": "load-first",
            "enabled": True,
        },
        blocking=True,
    )

    # Verify the API was called
    mock_growatt_api.min_write_time_segment.assert_called_once()


async def test_update_min_time_segment_discharge_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_growatt_api,
) -> None:
    """Test updating MIN time segment with discharge mode."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.growatt_server.get_device_list"
    ) as mock_get_devices:
        mock_get_devices.return_value = (
            [{"deviceSn": "MIN123456", "deviceType": "min"}],
            "12345",
        )
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        "update_min_time_segment",
        {
            "segment_id": 2,
            "start_time": "14:00",
            "end_time": "16:00",
            "batt_mode": "battery-first",
            "enabled": True,
        },
        blocking=True,
    )

    mock_growatt_api.min_write_time_segment.assert_called_once()


async def test_update_min_time_segment_standby_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_growatt_api,
) -> None:
    """Test updating MIN time segment with standby mode."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.growatt_server.get_device_list"
    ) as mock_get_devices:
        mock_get_devices.return_value = (
            [{"deviceSn": "MIN123456", "deviceType": "min"}],
            "12345",
        )
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        "update_min_time_segment",
        {
            "segment_id": 3,
            "start_time": "20:00",
            "end_time": "22:00",
            "batt_mode": "grid-first",
            "enabled": True,
        },
        blocking=True,
    )

    mock_growatt_api.min_write_time_segment.assert_called_once()


async def test_update_min_time_segment_disabled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_growatt_api,
) -> None:
    """Test disabling a MIN time segment."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.growatt_server.get_device_list"
    ) as mock_get_devices:
        mock_get_devices.return_value = (
            [{"deviceSn": "MIN123456", "deviceType": "min"}],
            "12345",
        )
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        "update_min_time_segment",
        {
            "segment_id": 1,
            "start_time": "06:00",
            "end_time": "08:00",
            "batt_mode": "load-first",
            "enabled": False,
        },
        blocking=True,
    )

    mock_growatt_api.min_write_time_segment.assert_called_once()


async def test_update_min_time_segment_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_growatt_api,
) -> None:
    """Test handling API error when updating MIN time segment."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.growatt_server.get_device_list"
    ) as mock_get_devices:
        mock_get_devices.return_value = (
            [{"deviceSn": "MIN123456", "deviceType": "min"}],
            "12345",
        )
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Mock API error response
    mock_growatt_api.min_write_time_segment.return_value = {
        "error_code": 1,
        "error_msg": "API Error",
    }

    with pytest.raises(HomeAssistantError, match="Error updating MIN time segment"):
        await hass.services.async_call(
            DOMAIN,
            "update_min_time_segment",
            {
                "segment_id": 1,
                "start_time": "09:00",
                "end_time": "11:00",
                "batt_mode": "load-first",
                "enabled": True,
            },
            blocking=True,
        )


async def test_no_min_devices_skips_service_registration(
    hass: HomeAssistant,
    mock_config_entry_classic: MockConfigEntry,
    mock_growatt_api,
) -> None:
    """Test that no services are registered when no MIN devices exist."""
    mock_config_entry_classic.add_to_hass(hass)

    with patch(
        "homeassistant.components.growatt_server.get_device_list"
    ) as mock_get_devices:
        # Only non-MIN devices (TLX with classic API)
        mock_get_devices.return_value = (
            [{"deviceSn": "TLX123456", "deviceType": "tlx"}],
            "12345",
        )
        assert await hass.config_entries.async_setup(mock_config_entry_classic.entry_id)
        await hass.async_block_till_done()

    # Verify services are not registered
    assert not hass.services.has_service(DOMAIN, "update_min_time_segment")
    assert not hass.services.has_service(DOMAIN, "read_min_time_segments")


async def test_multiple_devices_require_device_id_in_schema(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_growatt_api,
) -> None:
    """Test that multiple devices require device_id parameter in schema."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.growatt_server.get_device_list"
    ) as mock_get_devices:
        mock_get_devices.return_value = (
            [
                {"deviceSn": "MIN123456", "deviceType": "min"},
                {"deviceSn": "MIN789012", "deviceType": "min"},
            ],
            "12345",
        )
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Verify services are registered
    assert hass.services.has_service(DOMAIN, "update_min_time_segment")
    assert hass.services.has_service(DOMAIN, "read_min_time_segments")

    # Test that schema validation requires device_id for update service
    with pytest.raises(vol.MultipleInvalid, match="required key not provided"):
        await hass.services.async_call(
            DOMAIN,
            "update_min_time_segment",
            {
                # Missing required device_id
                "segment_id": 1,
                "start_time": "09:00",
                "end_time": "11:00",
                "batt_mode": "load-first",
                "enabled": True,
            },
            blocking=True,
        )

    # Test that schema validation requires device_id for read service
    with pytest.raises(vol.MultipleInvalid, match="required key not provided"):
        await hass.services.async_call(
            DOMAIN,
            "read_min_time_segments",
            {},  # Missing required device_id
            blocking=True,
            return_response=True,
        )


async def test_single_device_does_not_require_device_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_growatt_api,
) -> None:
    """Test that single device works without device_id parameter."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.growatt_server.get_device_list"
    ) as mock_get_devices:
        mock_get_devices.return_value = (
            [{"deviceSn": "MIN123456", "deviceType": "min"}],
            "12345",
        )
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Test update service works without device_id (single device)
    await hass.services.async_call(
        DOMAIN,
        "update_min_time_segment",
        {
            "segment_id": 1,
            "start_time": "09:00",
            "end_time": "11:00",
            "batt_mode": "load-first",
            "enabled": True,
        },
        blocking=True,
    )

    mock_growatt_api.min_write_time_segment.assert_called()

    # Test read service works without device_id (single device)
    response = await hass.services.async_call(
        DOMAIN,
        "read_min_time_segments",
        {},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    assert "time_segments" in response


async def test_multiple_devices_with_valid_device_id_works(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_growatt_api,
) -> None:
    """Test that multiple devices work when device_id is specified."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.growatt_server.get_device_list"
    ) as mock_get_devices:
        mock_get_devices.return_value = (
            [
                {"deviceSn": "MIN123456", "deviceType": "min"},
                {"deviceSn": "MIN789012", "deviceType": "min"},
            ],
            "12345",
        )
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Test update service with specific device_id
    await hass.services.async_call(
        DOMAIN,
        "update_min_time_segment",
        {
            "device_id": "MIN123456",
            "segment_id": 1,
            "start_time": "09:00",
            "end_time": "11:00",
            "batt_mode": "load-first",
            "enabled": True,
        },
        blocking=True,
    )

    mock_growatt_api.min_write_time_segment.assert_called_once()

    # Test read service with specific device_id
    response = await hass.services.async_call(
        DOMAIN,
        "read_min_time_segments",
        {"device_id": "MIN123456"},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    assert "time_segments" in response
