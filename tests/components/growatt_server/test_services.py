"""Test Growatt Server services."""

from unittest.mock import patch

import growattServer
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.growatt_server.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_growatt_v1_api")
async def test_read_time_segments_single_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test reading time segments for single device."""
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

    # Get the device registry ID
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "MIN123456")})
    assert device_entry is not None

    # Test service call
    response = await hass.services.async_call(
        DOMAIN,
        "read_time_segments",
        {"device_id": device_entry.id},
        blocking=True,
        return_response=True,
    )

    assert response == snapshot


async def test_update_time_segment_charge_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_growatt_v1_api,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test updating time segment with charge mode."""
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

    # Get the device registry ID
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "MIN123456")})
    assert device_entry is not None

    # Test successful update
    await hass.services.async_call(
        DOMAIN,
        "update_time_segment",
        {
            "device_id": device_entry.id,
            "segment_id": 1,
            "start_time": "09:00",
            "end_time": "11:00",
            "batt_mode": "load_first",
            "enabled": True,
        },
        blocking=True,
    )

    # Verify the API was called
    mock_growatt_v1_api.min_write_time_segment.assert_called_once()


async def test_update_time_segment_discharge_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_growatt_v1_api,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test updating time segment with discharge mode."""
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

    # Get the device registry ID
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "MIN123456")})
    assert device_entry is not None

    await hass.services.async_call(
        DOMAIN,
        "update_time_segment",
        {
            "device_id": device_entry.id,
            "segment_id": 2,
            "start_time": "14:00",
            "end_time": "16:00",
            "batt_mode": "battery_first",
            "enabled": True,
        },
        blocking=True,
    )

    mock_growatt_v1_api.min_write_time_segment.assert_called_once()


async def test_update_time_segment_standby_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_growatt_v1_api,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test updating time segment with standby mode."""
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

    # Get the device registry ID
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "MIN123456")})
    assert device_entry is not None

    await hass.services.async_call(
        DOMAIN,
        "update_time_segment",
        {
            "device_id": device_entry.id,
            "segment_id": 3,
            "start_time": "20:00",
            "end_time": "22:00",
            "batt_mode": "grid_first",
            "enabled": True,
        },
        blocking=True,
    )

    mock_growatt_v1_api.min_write_time_segment.assert_called_once()


async def test_update_time_segment_disabled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_growatt_v1_api,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test disabling a time segment."""
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

    # Get the device registry ID
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "MIN123456")})
    assert device_entry is not None

    await hass.services.async_call(
        DOMAIN,
        "update_time_segment",
        {
            "device_id": device_entry.id,
            "segment_id": 1,
            "start_time": "06:00",
            "end_time": "08:00",
            "batt_mode": "load_first",
            "enabled": False,
        },
        blocking=True,
    )

    mock_growatt_v1_api.min_write_time_segment.assert_called_once()


async def test_update_time_segment_with_seconds(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_growatt_v1_api,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test updating time segment with HH:MM:SS format from UI."""
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

    # Get the device registry ID
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "MIN123456")})
    assert device_entry is not None

    # Test with HH:MM:SS format (what the UI time selector sends)
    await hass.services.async_call(
        DOMAIN,
        "update_time_segment",
        {
            "device_id": device_entry.id,
            "segment_id": 1,
            "start_time": "09:00:00",
            "end_time": "11:00:00",
            "batt_mode": "load_first",
            "enabled": True,
        },
        blocking=True,
    )

    mock_growatt_v1_api.min_write_time_segment.assert_called_once()


async def test_update_time_segment_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_growatt_v1_api,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test handling API error when updating time segment."""
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

    # Get the device registry ID
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "MIN123456")})
    assert device_entry is not None

    # Mock API error - the library raises an exception instead of returning error dict
    mock_growatt_v1_api.min_write_time_segment.side_effect = (
        growattServer.GrowattV1ApiError(
            "Error during writing time segment 1",
            error_code=1,
            error_msg="API Error",
        )
    )

    with pytest.raises(HomeAssistantError, match="API error updating time segment"):
        await hass.services.async_call(
            DOMAIN,
            "update_time_segment",
            {
                "device_id": device_entry.id,
                "segment_id": 1,
                "start_time": "09:00",
                "end_time": "11:00",
                "batt_mode": "load_first",
                "enabled": True,
            },
            blocking=True,
        )


@pytest.mark.usefixtures("mock_growatt_classic_api")
async def test_no_min_devices_skips_service_registration(
    hass: HomeAssistant,
    mock_config_entry_classic: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that services fail gracefully when no MIN devices exist."""
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

    # Verify services are registered (they're always registered in async_setup)
    assert hass.services.has_service(DOMAIN, "update_time_segment")
    assert hass.services.has_service(DOMAIN, "read_time_segments")

    # Get the TLX device (non-MIN)
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "TLX123456")})
    assert device_entry is not None

    # But calling them with a non-MIN device should fail with appropriate error
    with pytest.raises(
        ServiceValidationError, match="No MIN devices with token authentication"
    ):
        await hass.services.async_call(
            DOMAIN,
            "update_time_segment",
            {
                "device_id": device_entry.id,
                "segment_id": 1,
                "start_time": "09:00",
                "end_time": "11:00",
                "batt_mode": "load_first",
                "enabled": True,
            },
            blocking=True,
        )


async def test_multiple_devices_with_valid_device_id_works(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_growatt_v1_api,
    device_registry: dr.DeviceRegistry,
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

    # Get the device registry ID for the first MIN device
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "MIN123456")})
    assert device_entry is not None

    # Test update service with specific device_id (device registry ID)
    await hass.services.async_call(
        DOMAIN,
        "update_time_segment",
        {
            "device_id": device_entry.id,
            "segment_id": 1,
            "start_time": "09:00",
            "end_time": "11:00",
            "batt_mode": "load_first",
            "enabled": True,
        },
        blocking=True,
    )

    mock_growatt_v1_api.min_write_time_segment.assert_called_once()

    # Test read service with specific device_id (device registry ID)
    response = await hass.services.async_call(
        DOMAIN,
        "read_time_segments",
        {"device_id": device_entry.id},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    assert "time_segments" in response


@pytest.mark.usefixtures("mock_growatt_v1_api")
async def test_update_time_segment_invalid_time_format(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test handling invalid time format in update_time_segment."""
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

    # Get the device registry ID
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "MIN123456")})
    assert device_entry is not None

    # Test with invalid time format
    with pytest.raises(
        ServiceValidationError, match="start_time must be in HH:MM or HH:MM:SS format"
    ):
        await hass.services.async_call(
            DOMAIN,
            "update_time_segment",
            {
                "device_id": device_entry.id,
                "segment_id": 1,
                "start_time": "invalid",
                "end_time": "11:00",
                "batt_mode": "load_first",
                "enabled": True,
            },
            blocking=True,
        )


@pytest.mark.usefixtures("mock_growatt_v1_api")
async def test_update_time_segment_invalid_segment_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test validation of segment_id range."""
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

    # Get the device registry ID
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "MIN123456")})
    assert device_entry is not None

    # Test segment_id too low
    with pytest.raises(
        ServiceValidationError, match="segment_id must be between 1 and 9"
    ):
        await hass.services.async_call(
            DOMAIN,
            "update_time_segment",
            {
                "device_id": device_entry.id,
                "segment_id": 0,
                "start_time": "09:00",
                "end_time": "11:00",
                "batt_mode": "load_first",
                "enabled": True,
            },
            blocking=True,
        )

    # Test segment_id too high
    with pytest.raises(
        ServiceValidationError, match="segment_id must be between 1 and 9"
    ):
        await hass.services.async_call(
            DOMAIN,
            "update_time_segment",
            {
                "device_id": device_entry.id,
                "segment_id": 10,
                "start_time": "09:00",
                "end_time": "11:00",
                "batt_mode": "load_first",
                "enabled": True,
            },
            blocking=True,
        )


@pytest.mark.usefixtures("mock_growatt_v1_api")
async def test_update_time_segment_invalid_batt_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test validation of batt_mode value."""
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

    # Get the device registry ID
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "MIN123456")})
    assert device_entry is not None

    # Test invalid batt_mode
    with pytest.raises(ServiceValidationError, match="batt_mode must be one of"):
        await hass.services.async_call(
            DOMAIN,
            "update_time_segment",
            {
                "device_id": device_entry.id,
                "segment_id": 1,
                "start_time": "09:00",
                "end_time": "11:00",
                "batt_mode": "invalid_mode",
                "enabled": True,
            },
            blocking=True,
        )


@pytest.mark.usefixtures("mock_growatt_v1_api")
async def test_read_time_segments_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test handling API error when reading time segments."""
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

    # Get the device registry ID
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "MIN123456")})
    assert device_entry is not None

    # Mock API error by making coordinator.read_time_segments raise an exception
    with (
        patch(
            "homeassistant.components.growatt_server.coordinator.GrowattCoordinator.read_time_segments",
            side_effect=HomeAssistantError("API connection failed"),
        ),
        pytest.raises(HomeAssistantError, match="API connection failed"),
    ):
        await hass.services.async_call(
            DOMAIN,
            "read_time_segments",
            {"device_id": device_entry.id},
            blocking=True,
            return_response=True,
        )
