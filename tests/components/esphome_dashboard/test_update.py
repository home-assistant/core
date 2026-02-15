"""Test the ESPHome Dashboard update platform."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from aioesphomeapi import APIConnectionError
import pytest

from homeassistant.components.esphome_dashboard.const import DOMAIN
from homeassistant.components.esphome_dashboard.update import (
    ESPHomeDashboardUpdateEntity,
)
from homeassistant.components.update import SERVICE_INSTALL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, CONF_URL, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from tests.common import MockConfigEntry


async def test_update_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test update entities are created correctly."""
    # Check that update entities are created (entity name is "Firmware" from device name)
    state = hass.states.get("update.test_device_firmware")
    assert state is not None
    assert state.state == STATE_ON  # Update available (deployed != current)
    assert state.attributes["installed_version"] == "2023.12.0"  # deployed_version
    assert state.attributes["latest_version"] == "2024.1.0"  # current_version

    state2 = hass.states.get("update.test_device_2_firmware")
    assert state2 is not None
    assert state2.state == STATE_OFF  # No update available (deployed == current)
    assert state2.attributes["installed_version"] == "2023.11.0"  # deployed_version
    assert state2.attributes["latest_version"] == "2023.11.0"  # current_version

    # Verify entity registry entries
    entry = entity_registry.async_get("update.test_device_firmware")
    assert entry
    assert entry.unique_id == f"{init_integration.entry_id}_test_device"

    entry2 = entity_registry.async_get("update.test_device_2_firmware")
    assert entry2
    assert entry2.unique_id == f"{init_integration.entry_id}_test_device_2"


async def test_update_entity_device_removed(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_dashboard_api
) -> None:
    """Test update entity when device is removed from dashboard."""
    # Initially device exists
    state = hass.states.get("update.test_device_firmware")
    assert state is not None
    assert state.state == STATE_ON

    # Update coordinator data to remove device
    mock_dashboard_api.get_devices = AsyncMock(
        return_value={
            "configured": [
                {
                    "name": "test_device_2",
                    "deployed_version": "2023.11.0",
                    "current_version": "2023.11.0",
                    "configuration": "test_device_2.yaml",
                }
            ]
        }
    )

    # Trigger coordinator update
    coordinator = init_integration.runtime_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Entity should now be unavailable
    state = hass.states.get("update.test_device_firmware")
    assert state is not None
    assert state.state == "unavailable"


async def test_coordinator_update_failure(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_dashboard_api
) -> None:
    """Test coordinator update failure."""
    # Initially entities are available
    state = hass.states.get("update.test_device_firmware")
    assert state is not None
    assert state.state == STATE_ON

    # Make API fail
    mock_dashboard_api.get_devices = AsyncMock(
        side_effect=Exception("Connection error")
    )

    # Trigger coordinator update
    coordinator = init_integration.runtime_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Entities should become unavailable
    state = hass.states.get("update.test_device_firmware")
    assert state is not None
    assert state.state == "unavailable"


async def test_dynamic_device_addition(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_dashboard_api
) -> None:
    """Test that new devices are added dynamically."""
    # Initially two devices
    state = hass.states.get("update.test_device_firmware")
    assert state is not None
    state2 = hass.states.get("update.test_device_2_firmware")
    assert state2 is not None

    # No third device yet
    state3 = hass.states.get("update.test_device_3_firmware")
    assert state3 is None

    # Update coordinator data to add a new device
    mock_dashboard_api.get_devices = AsyncMock(
        return_value={
            "configured": [
                {
                    "name": "test_device",
                    "deployed_version": "2023.12.0",
                    "current_version": "2024.1.0",
                    "configuration": "test_device.yaml",
                },
                {
                    "name": "test_device_2",
                    "deployed_version": "2023.11.0",
                    "current_version": "2023.11.0",
                    "configuration": "test_device_2.yaml",
                },
                {
                    "name": "test_device_3",
                    "deployed_version": "2024.2.0",
                    "current_version": "2024.2.0",
                    "configuration": "test_device_3.yaml",
                },
            ]
        }
    )

    # Trigger coordinator update
    coordinator = init_integration.runtime_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Third device should now exist
    state3 = hass.states.get("update.test_device_3_firmware")
    assert state3 is not None
    assert state3.state == STATE_OFF
    assert state3.attributes["installed_version"] == "2024.2.0"


async def test_update_entity_with_mac_address(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test update entity links to existing ESPHome device via MAC address."""
    # First create a fake ESPHome config entry to register the device
    esphome_entry = MockConfigEntry(
        domain="esphome",
        data={},
        unique_id="esphome_device_1",
    )
    esphome_entry.add_to_hass(hass)

    # Create an existing ESPHome device with MAC address
    existing_device = device_registry.async_get_or_create(
        config_entry_id=esphome_entry.entry_id,
        connections={(CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff")},
        name="test_device",
        manufacturer="ESPHome",
    )

    # Create mock API that returns device data
    mock_api = MagicMock()
    mock_api.request = AsyncMock(return_value=None)
    mock_api.get_devices = AsyncMock(
        return_value={
            "configured": [
                {
                    "name": "test_device",
                    "deployed_version": "2024.1.0",
                    "current_version": "2024.1.0",
                    "configuration": "test_device.yaml",
                }
            ]
        }
    )

    # Create config entry
    entry = MockConfigEntry(
        title="ESPHome Dashboard",
        domain=DOMAIN,
        data={CONF_URL: "http://192.168.1.100:6052"},
        unique_id="http://192.168.1.100:6052",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.esphome_dashboard.ESPHomeDashboardAPI",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # The update entity should be linked to the existing device via MAC
    update_entity = entity_registry.async_get("update.test_device_firmware")
    assert update_entity is not None
    assert update_entity.device_id == existing_device.id


async def test_update_entity_install_success(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test successful firmware installation via update entity."""
    # Create mock API with compile and upload methods
    mock_api = MagicMock()
    mock_api.request = AsyncMock(return_value=None)
    mock_api.get_devices = AsyncMock(
        return_value={
            "configured": [
                {
                    "name": "test_device",
                    "deployed_version": "2024.1.0",
                    "current_version": "2024.2.0",
                    "configuration": "test_device.yaml",
                    "address": "192.168.1.50",
                }
            ]
        }
    )
    mock_api.compile = AsyncMock(return_value=True)
    mock_api.upload = AsyncMock(return_value=True)

    # Create config entry
    entry = MockConfigEntry(
        title="ESPHome Dashboard",
        domain=DOMAIN,
        data={CONF_URL: "http://192.168.1.100:6052"},
        unique_id="http://192.168.1.100:6052",
    )
    entry.add_to_hass(hass)

    # Mock mDNS port discovery to return None (fall back to default port)
    mock_discover_port = AsyncMock(return_value=None)

    # Mock direct API client for version query
    mock_device_info = MagicMock()
    mock_device_info.esphome_version = "2024.1.0"

    mock_api_client = MagicMock()
    mock_api_client.connect = AsyncMock()
    mock_api_client.disconnect = AsyncMock()
    mock_api_client.device_info = AsyncMock(return_value=mock_device_info)

    mock_zeroconf = MagicMock()

    with (
        patch(
            "homeassistant.components.esphome_dashboard.ESPHomeDashboardAPI",
            return_value=mock_api,
        ),
        patch(
            "homeassistant.components.esphome_dashboard.update.APIClient",
            return_value=mock_api_client,
        ),
        patch.object(
            ESPHomeDashboardUpdateEntity,
            "_async_discover_device_port",
            mock_discover_port,
        ),
        patch(
            "homeassistant.components.esphome_dashboard.update.zeroconf.async_get_instance",
            return_value=mock_zeroconf,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Entity should have install feature enabled
        state = hass.states.get("update.test_device_firmware")
        assert state is not None
        assert state.state == STATE_ON  # Update available

        # Call install service
        await hass.services.async_call(
            "update",
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.test_device_firmware"},
            blocking=True,
        )

        # Verify compile and upload were called
        mock_api.compile.assert_called_once_with("test_device.yaml")
        mock_api.upload.assert_called_once_with("test_device.yaml", "192.168.1.50")


async def test_update_entity_no_address_no_install_support(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test update entity without address doesn't support install."""
    # Create mock API without address in device data
    mock_api = MagicMock()
    mock_api.request = AsyncMock(return_value=None)
    mock_api.get_devices = AsyncMock(
        return_value={
            "configured": [
                {
                    "name": "test_device",
                    "deployed_version": "2024.1.0",
                    "current_version": "2024.2.0",
                    "configuration": "test_device.yaml",
                    # No address field
                }
            ]
        }
    )

    # Create config entry
    entry = MockConfigEntry(
        title="ESPHome Dashboard",
        domain=DOMAIN,
        data={CONF_URL: "http://192.168.1.100:6052"},
        unique_id="http://192.168.1.100:6052",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.esphome_dashboard.ESPHomeDashboardAPI",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Entity should exist but install feature should not be enabled (no address)
    state = hass.states.get("update.test_device_firmware")
    assert state is not None
    # No install feature when there's no address
    assert state.attributes.get("supported_features", 0) == 0


async def test_update_entity_install_address_cleared(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test async_install raises error when address becomes unavailable."""
    # Create mock API that initially has address, then loses it
    mock_api = MagicMock()
    mock_api.request = AsyncMock(return_value=None)
    mock_api.get_devices = AsyncMock(
        return_value={
            "configured": [
                {
                    "name": "test_device",
                    "deployed_version": "2024.1.0",
                    "current_version": "2024.2.0",
                    "configuration": "test_device.yaml",
                    "address": "192.168.1.50",
                }
            ]
        }
    )

    # Create config entry
    entry = MockConfigEntry(
        title="ESPHome Dashboard",
        domain=DOMAIN,
        data={CONF_URL: "http://192.168.1.100:6052"},
        unique_id="http://192.168.1.100:6052",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.esphome_dashboard.ESPHomeDashboardAPI",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Entity should have install support
        state = hass.states.get("update.test_device_firmware")
        assert state is not None

        # Get the entity directly to call async_install
        entity_id = "update.test_device_firmware"
        entity_entry = entity_registry.async_get(entity_id)
        assert entity_entry is not None

        # Get entity object to directly test async_install
        entity: ESPHomeDashboardUpdateEntity = hass.data["update"].get_entity(entity_id)
        assert entity is not None

        # Manually clear the address to simulate it becoming unavailable
        entity._address = None

        # Now try to install - should fail because address is gone
        with pytest.raises(HomeAssistantError, match="no address available"):
            await entity.async_install(version=None, backup=False)


async def test_update_entity_install_compile_failure(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test firmware installation fails when compilation fails."""
    # Create mock API with compile failure
    mock_api = MagicMock()
    mock_api.request = AsyncMock(return_value=None)
    mock_api.get_devices = AsyncMock(
        return_value={
            "configured": [
                {
                    "name": "test_device",
                    "deployed_version": "2024.1.0",
                    "current_version": "2024.2.0",
                    "configuration": "test_device.yaml",
                    "address": "192.168.1.50",
                }
            ]
        }
    )
    mock_api.compile = AsyncMock(return_value=False)  # Compile fails

    # Create config entry
    entry = MockConfigEntry(
        title="ESPHome Dashboard",
        domain=DOMAIN,
        data={CONF_URL: "http://192.168.1.100:6052"},
        unique_id="http://192.168.1.100:6052",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.esphome_dashboard.ESPHomeDashboardAPI",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # The install service should raise an error
    with pytest.raises(HomeAssistantError, match="Failed to compile"):
        await hass.services.async_call(
            "update",
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.test_device_firmware"},
            blocking=True,
        )


async def test_update_entity_install_upload_failure(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test firmware installation fails when upload fails."""
    # Create mock API with upload failure
    mock_api = MagicMock()
    mock_api.request = AsyncMock(return_value=None)
    mock_api.get_devices = AsyncMock(
        return_value={
            "configured": [
                {
                    "name": "test_device",
                    "deployed_version": "2024.1.0",
                    "current_version": "2024.2.0",
                    "configuration": "test_device.yaml",
                    "address": "192.168.1.50",
                }
            ]
        }
    )
    mock_api.compile = AsyncMock(return_value=True)
    mock_api.upload = AsyncMock(return_value=False)  # Upload fails

    # Create config entry
    entry = MockConfigEntry(
        title="ESPHome Dashboard",
        domain=DOMAIN,
        data={CONF_URL: "http://192.168.1.100:6052"},
        unique_id="http://192.168.1.100:6052",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.esphome_dashboard.ESPHomeDashboardAPI",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # The install service should raise an error
    with pytest.raises(HomeAssistantError, match="Failed to upload"):
        await hass.services.async_call(
            "update",
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.test_device_firmware"},
            blocking=True,
        )


async def test_installed_version_fallback_to_dashboard(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test installed_version falls back to dashboard when direct query fails.

    When a device is NOT in the esphome integration and the direct API query
    fails (device offline, encrypted, etc.), fall back to dashboard's deployed_version.
    """
    dashboard_deployed_version = "2023.12.0"
    dashboard_current_version = "2024.5.0"

    # Create mock dashboard API
    mock_api = MagicMock()
    mock_api.request = AsyncMock(return_value=None)
    mock_api.get_devices = AsyncMock(
        return_value={
            "configured": [
                {
                    "name": "test_device",
                    "deployed_version": dashboard_deployed_version,
                    "current_version": dashboard_current_version,
                    "configuration": "test_device.yaml",
                    "address": "192.168.1.50",
                }
            ]
        }
    )

    # Create esphome_dashboard config entry
    entry = MockConfigEntry(
        title="ESPHome Dashboard",
        domain=DOMAIN,
        data={CONF_URL: "http://192.168.1.100:6052"},
        unique_id="http://192.168.1.100:6052",
    )
    entry.add_to_hass(hass)

    # Mock the direct API query to fail (device offline/encrypted)
    mock_api_client = MagicMock()
    mock_api_client.connect = AsyncMock(
        side_effect=APIConnectionError("Connection failed")
    )
    mock_api_client.disconnect = AsyncMock()

    # Mock mDNS port discovery to return None (fall back to default port)
    mock_discover_port = AsyncMock(return_value=None)

    with (
        patch(
            "homeassistant.components.esphome_dashboard.ESPHomeDashboardAPI",
            return_value=mock_api,
        ),
        patch(
            "homeassistant.components.esphome_dashboard.update.APIClient",
            return_value=mock_api_client,
        ),
        patch.object(
            ESPHomeDashboardUpdateEntity,
            "_async_discover_device_port",
            mock_discover_port,
        ),
        patch(
            "homeassistant.components.esphome_dashboard.update.zeroconf.async_get_instance",
            return_value=MagicMock(),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Should fall back to dashboard's deployed_version when query fails
    state = hass.states.get("update.test_device_firmware")
    assert state is not None
    assert state.attributes["installed_version"] == dashboard_deployed_version
    assert state.attributes["latest_version"] == dashboard_current_version


async def test_installed_version_from_direct_api_query(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test installed_version from direct native API query.

    When a device is NOT in the esphome integration, we should query the
    device directly via the native API to get the actual version.
    """
    # The dashboard reports deployed_version as "2023.12.0" but the actual
    # device (via direct API query) reports version "2024.3.0"
    dashboard_deployed_version = "2023.12.0"
    actual_device_version = "2024.3.0"
    dashboard_current_version = "2024.5.0"

    # Create mock dashboard API
    mock_api = MagicMock()
    mock_api.request = AsyncMock(return_value=None)
    mock_api.get_devices = AsyncMock(
        return_value={
            "configured": [
                {
                    "name": "test_device",
                    "deployed_version": dashboard_deployed_version,
                    "current_version": dashboard_current_version,
                    "configuration": "test_device.yaml",
                    "address": "192.168.1.50",
                }
            ]
        }
    )

    # Create esphome_dashboard config entry
    entry = MockConfigEntry(
        title="ESPHome Dashboard",
        domain=DOMAIN,
        data={CONF_URL: "http://192.168.1.100:6052"},
        unique_id="http://192.168.1.100:6052",
    )
    entry.add_to_hass(hass)

    # Mock the direct API query
    mock_device_info = MagicMock()
    mock_device_info.esphome_version = actual_device_version

    mock_api_client = MagicMock()
    mock_api_client.connect = AsyncMock()
    mock_api_client.disconnect = AsyncMock()
    mock_api_client.device_info = AsyncMock(return_value=mock_device_info)

    # Mock mDNS port discovery to return None (fall back to default port)
    mock_discover_port = AsyncMock(return_value=None)

    with (
        patch(
            "homeassistant.components.esphome_dashboard.ESPHomeDashboardAPI",
            return_value=mock_api,
        ),
        patch(
            "homeassistant.components.esphome_dashboard.update.APIClient",
            return_value=mock_api_client,
        ),
        patch.object(
            ESPHomeDashboardUpdateEntity,
            "_async_discover_device_port",
            mock_discover_port,
        ),
        patch(
            "homeassistant.components.esphome_dashboard.update.zeroconf.async_get_instance",
            return_value=MagicMock(),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # The installed_version should be from direct API query (actual device version)
    # NOT the dashboard's deployed_version
    state = hass.states.get("update.test_device_firmware")
    assert state is not None
    assert state.attributes["installed_version"] == actual_device_version
    assert state.attributes["latest_version"] == dashboard_current_version


async def test_post_ota_version_refresh(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that cached version is refreshed after OTA update.

    When an OTA update is performed via the dashboard, the cached version
    should be cleared and re-queried from the device.
    """
    initial_version = "2024.1.0"
    updated_version = "2024.5.0"

    # Create mock dashboard API
    mock_api = MagicMock()
    mock_api.request = AsyncMock(return_value=None)
    mock_api.get_devices = AsyncMock(
        return_value={
            "configured": [
                {
                    "name": "test_device",
                    "deployed_version": "2023.12.0",  # Stale version
                    "current_version": updated_version,
                    "configuration": "test_device.yaml",
                    "address": "192.168.1.50",
                }
            ]
        }
    )
    mock_api.compile = AsyncMock(return_value=True)
    mock_api.upload = AsyncMock(return_value=True)

    # Create esphome_dashboard config entry
    entry = MockConfigEntry(
        title="ESPHome Dashboard",
        domain=DOMAIN,
        data={CONF_URL: "http://192.168.1.100:6052"},
        unique_id="http://192.168.1.100:6052",
    )
    entry.add_to_hass(hass)

    # Track calls to the API client
    query_count = 0

    def create_mock_client(*args, **kwargs):
        nonlocal query_count
        mock_device_info = MagicMock()
        # Return initial version first, then updated version after OTA
        if query_count == 0:
            mock_device_info.esphome_version = initial_version
        else:
            mock_device_info.esphome_version = updated_version
        query_count += 1

        mock_client = MagicMock()
        mock_client.connect = AsyncMock()
        mock_client.disconnect = AsyncMock()
        mock_client.device_info = AsyncMock(return_value=mock_device_info)
        return mock_client

    # Mock mDNS port discovery to return None (fall back to default port)
    mock_discover_port = AsyncMock(return_value=None)

    with (
        patch(
            "homeassistant.components.esphome_dashboard.ESPHomeDashboardAPI",
            return_value=mock_api,
        ),
        patch(
            "homeassistant.components.esphome_dashboard.update.APIClient",
            side_effect=create_mock_client,
        ),
        patch.object(
            ESPHomeDashboardUpdateEntity,
            "_async_discover_device_port",
            mock_discover_port,
        ),
        patch(
            "homeassistant.components.esphome_dashboard.update.zeroconf.async_get_instance",
            return_value=MagicMock(),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Initial version from direct query
        state = hass.states.get("update.test_device_firmware")
        assert state is not None
        assert state.attributes["installed_version"] == initial_version

        # Perform OTA update
        await hass.services.async_call(
            "update",
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.test_device_firmware"},
            blocking=True,
        )

        # Wait for delayed version query (if any)
        await asyncio.sleep(0.1)
        await hass.async_block_till_done()

        # After OTA, version should be updated
        state = hass.states.get("update.test_device_firmware")
        assert state is not None
        assert state.attributes["installed_version"] == updated_version


async def test_installed_version_from_esphome_integration(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test installed_version uses esphome integration version when available.

    When a device is also configured in the esphome integration, the
    installed_version should come from device_info.esphome_version (the actual
    device version) instead of the dashboard's deployed_version (which can be stale).
    """
    # The dashboard reports deployed_version as "2023.12.0" but the actual
    # device (via esphome integration) reports version "2024.3.0"
    dashboard_deployed_version = "2023.12.0"
    actual_device_version = "2024.3.0"
    dashboard_current_version = "2024.5.0"  # Available update target

    # Create mock esphome config entry with RuntimeEntryData
    esphome_entry = MockConfigEntry(
        domain="esphome",
        data={
            "host": "192.168.1.50",
            "port": 6053,
            "password": "",
        },
        unique_id="11:22:33:44:55:aa",
    )
    esphome_entry.add_to_hass(hass)

    # Create mock RuntimeEntryData with device_info containing the actual version
    mock_device_info = MagicMock()
    mock_device_info.name = "test_device"
    mock_device_info.esphome_version = actual_device_version

    mock_entry_data = MagicMock()
    mock_entry_data.device_info = mock_device_info
    mock_entry_data.async_subscribe_device_updated = MagicMock(
        return_value=lambda: None
    )

    # Attach runtime_data to the entry
    esphome_entry.runtime_data = mock_entry_data

    # Mark the esphome entry as loaded
    hass.config_entries._entries[esphome_entry.entry_id] = esphome_entry
    esphome_entry._async_set_state(hass, ConfigEntryState.LOADED, None)

    # Create mock dashboard API
    mock_api = MagicMock()
    mock_api.request = AsyncMock(return_value=None)
    mock_api.get_devices = AsyncMock(
        return_value={
            "configured": [
                {
                    "name": "test_device",
                    "deployed_version": dashboard_deployed_version,
                    "current_version": dashboard_current_version,
                    "configuration": "test_device.yaml",
                    "address": "192.168.1.50",
                }
            ]
        }
    )

    # Create esphome_dashboard config entry
    entry = MockConfigEntry(
        title="ESPHome Dashboard",
        domain=DOMAIN,
        data={CONF_URL: "http://192.168.1.100:6052"},
        unique_id="http://192.168.1.100:6052",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.esphome_dashboard.ESPHomeDashboardAPI",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # The installed_version should be from esphome integration (actual device version)
    # NOT the dashboard's deployed_version
    state = hass.states.get("update.test_device_firmware")
    assert state is not None
    assert state.attributes["installed_version"] == actual_device_version
    assert state.attributes["latest_version"] == dashboard_current_version
    # Update should be available since actual version != current_version
    assert state.state == STATE_ON


async def test_mdns_port_discovery_success(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test successful mDNS port discovery for native API.

    When a device advertises its port via mDNS, we should use that port
    instead of the default port.
    """
    actual_device_version = "2024.3.0"
    discovered_port = 6055  # Non-default port

    # Create mock dashboard API
    mock_api = MagicMock()
    mock_api.request = AsyncMock(return_value=None)
    mock_api.get_devices = AsyncMock(
        return_value={
            "configured": [
                {
                    "name": "test_device",
                    "deployed_version": "2023.12.0",
                    "current_version": "2024.5.0",
                    "configuration": "test_device.yaml",
                    "address": "192.168.1.50",
                }
            ]
        }
    )

    # Create esphome_dashboard config entry
    entry = MockConfigEntry(
        title="ESPHome Dashboard",
        domain=DOMAIN,
        data={CONF_URL: "http://192.168.1.100:6052"},
        unique_id="http://192.168.1.100:6052",
    )
    entry.add_to_hass(hass)

    # Mock the direct API query
    mock_device_info = MagicMock()
    mock_device_info.esphome_version = actual_device_version

    mock_api_client = MagicMock()
    mock_api_client.connect = AsyncMock()
    mock_api_client.disconnect = AsyncMock()
    mock_api_client.device_info = AsyncMock(return_value=mock_device_info)

    # Mock mDNS discovery to return a non-default port
    mock_service_info = MagicMock()
    mock_service_info.port = discovered_port
    mock_service_info.async_request = AsyncMock(return_value=True)

    mock_aiozc = MagicMock()
    mock_zeroconf = MagicMock()

    with (
        patch(
            "homeassistant.components.esphome_dashboard.ESPHomeDashboardAPI",
            return_value=mock_api,
        ),
        patch(
            "homeassistant.components.esphome_dashboard.update.APIClient",
            return_value=mock_api_client,
        ) as mock_api_client_class,
        patch(
            "homeassistant.components.esphome_dashboard.update.zeroconf.async_get_async_instance",
            return_value=mock_aiozc,
        ),
        patch(
            "homeassistant.components.esphome_dashboard.update.zeroconf.async_get_instance",
            return_value=mock_zeroconf,
        ),
        patch(
            "homeassistant.components.esphome_dashboard.update.AsyncServiceInfo",
            return_value=mock_service_info,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # The API client should have been created with the discovered port and shared zeroconf
    mock_api_client_class.assert_called_with(
        "192.168.1.50",
        port=discovered_port,
        password="",
        zeroconf_instance=mock_zeroconf,
    )

    # Version should be from the direct query
    state = hass.states.get("update.test_device_firmware")
    assert state is not None
    assert state.attributes["installed_version"] == actual_device_version


async def test_mdns_port_discovery_failure(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test mDNS port discovery failure falls back to default port.

    When mDNS discovery fails (timeout, OS error, etc.), we should fall back
    to the default ESPHome native API port.
    """
    actual_device_version = "2024.3.0"

    # Create mock dashboard API
    mock_api = MagicMock()
    mock_api.request = AsyncMock(return_value=None)
    mock_api.get_devices = AsyncMock(
        return_value={
            "configured": [
                {
                    "name": "test_device",
                    "deployed_version": "2023.12.0",
                    "current_version": "2024.5.0",
                    "configuration": "test_device.yaml",
                    "address": "192.168.1.50",
                }
            ]
        }
    )

    # Create esphome_dashboard config entry
    entry = MockConfigEntry(
        title="ESPHome Dashboard",
        domain=DOMAIN,
        data={CONF_URL: "http://192.168.1.100:6052"},
        unique_id="http://192.168.1.100:6052",
    )
    entry.add_to_hass(hass)

    # Mock the direct API query
    mock_device_info = MagicMock()
    mock_device_info.esphome_version = actual_device_version

    mock_api_client = MagicMock()
    mock_api_client.connect = AsyncMock()
    mock_api_client.disconnect = AsyncMock()
    mock_api_client.device_info = AsyncMock(return_value=mock_device_info)

    # Mock mDNS discovery to raise TimeoutError
    mock_zeroconf = MagicMock()

    with (
        patch(
            "homeassistant.components.esphome_dashboard.ESPHomeDashboardAPI",
            return_value=mock_api,
        ),
        patch(
            "homeassistant.components.esphome_dashboard.update.APIClient",
            return_value=mock_api_client,
        ) as mock_api_client_class,
        patch(
            "homeassistant.components.esphome_dashboard.update.zeroconf.async_get_async_instance",
            side_effect=TimeoutError("mDNS timeout"),
        ),
        patch(
            "homeassistant.components.esphome_dashboard.update.zeroconf.async_get_instance",
            return_value=mock_zeroconf,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # The API client should have been created with the default port and shared zeroconf
    mock_api_client_class.assert_called_with(
        "192.168.1.50", port=6053, password="", zeroconf_instance=mock_zeroconf
    )

    # Version should still be from the direct query
    state = hass.states.get("update.test_device_firmware")
    assert state is not None
    assert state.attributes["installed_version"] == actual_device_version


async def test_esphome_device_update_callback(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that esphome device update callback triggers state update.

    When the esphome integration reports a device update (e.g., version change),
    the update entity should update its state.
    """
    initial_version = "2024.1.0"
    updated_version = "2024.5.0"

    # Create mock esphome config entry with RuntimeEntryData
    esphome_entry = MockConfigEntry(
        domain="esphome",
        data={
            "host": "192.168.1.50",
            "port": 6053,
            "password": "",
        },
        unique_id="11:22:33:44:55:aa",
    )
    esphome_entry.add_to_hass(hass)

    # Create mock device_info that we can update
    mock_device_info = MagicMock()
    mock_device_info.name = "test_device"
    mock_device_info.esphome_version = initial_version

    # Store the callback so we can call it later
    update_callbacks = []

    def mock_subscribe(callback):
        update_callbacks.append(callback)
        return lambda: update_callbacks.remove(callback)

    mock_entry_data = MagicMock()
    mock_entry_data.device_info = mock_device_info
    mock_entry_data.async_subscribe_device_updated = mock_subscribe

    # Attach runtime_data to the entry
    esphome_entry.runtime_data = mock_entry_data

    # Mark the esphome entry as loaded
    hass.config_entries._entries[esphome_entry.entry_id] = esphome_entry
    esphome_entry._async_set_state(hass, ConfigEntryState.LOADED, None)

    # Create mock dashboard API
    mock_api = MagicMock()
    mock_api.request = AsyncMock(return_value=None)
    mock_api.get_devices = AsyncMock(
        return_value={
            "configured": [
                {
                    "name": "test_device",
                    "deployed_version": "2023.12.0",
                    "current_version": "2024.6.0",
                    "configuration": "test_device.yaml",
                    "address": "192.168.1.50",
                }
            ]
        }
    )

    # Create esphome_dashboard config entry
    entry = MockConfigEntry(
        title="ESPHome Dashboard",
        domain=DOMAIN,
        data={CONF_URL: "http://192.168.1.100:6052"},
        unique_id="http://192.168.1.100:6052",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.esphome_dashboard.ESPHomeDashboardAPI",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Initial version from esphome integration
    state = hass.states.get("update.test_device_firmware")
    assert state is not None
    assert state.attributes["installed_version"] == initial_version

    # Simulate device update from esphome integration
    mock_device_info.esphome_version = updated_version

    # Call the update callback
    assert len(update_callbacks) == 1
    update_callbacks[0]()
    await hass.async_block_till_done()

    # Version should now be updated
    state = hass.states.get("update.test_device_firmware")
    assert state is not None
    assert state.attributes["installed_version"] == updated_version


async def test_dynamic_esphome_discovery_on_coordinator_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test dynamic esphome integration discovery on coordinator update.

    When the esphome integration loads after esphome_dashboard, the update
    entity should detect it on the next coordinator update and switch to
    using the esphome integration version.
    """
    dashboard_version = "2023.12.0"
    esphome_version = "2024.3.0"

    # Create mock dashboard API
    mock_api = MagicMock()
    mock_api.request = AsyncMock(return_value=None)
    mock_api.get_devices = AsyncMock(
        return_value={
            "configured": [
                {
                    "name": "test_device",
                    "deployed_version": dashboard_version,
                    "current_version": "2024.5.0",
                    "configuration": "test_device.yaml",
                    # No address - so direct query won't be attempted
                }
            ]
        }
    )

    # Create esphome_dashboard config entry FIRST (before esphome)
    entry = MockConfigEntry(
        title="ESPHome Dashboard",
        domain=DOMAIN,
        data={CONF_URL: "http://192.168.1.100:6052"},
        unique_id="http://192.168.1.100:6052",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.esphome_dashboard.ESPHomeDashboardAPI",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Initially should use dashboard version (no esphome integration yet)
    state = hass.states.get("update.test_device_firmware")
    assert state is not None
    assert state.attributes["installed_version"] == dashboard_version

    # Now "load" esphome integration
    esphome_entry = MockConfigEntry(
        domain="esphome",
        data={
            "host": "192.168.1.50",
            "port": 6053,
            "password": "",
        },
        unique_id="11:22:33:44:55:bb",
    )
    esphome_entry.add_to_hass(hass)

    mock_device_info = MagicMock()
    mock_device_info.name = "test_device"
    mock_device_info.esphome_version = esphome_version

    mock_entry_data = MagicMock()
    mock_entry_data.device_info = mock_device_info
    mock_entry_data.async_subscribe_device_updated = MagicMock(
        return_value=lambda: None
    )

    esphome_entry.runtime_data = mock_entry_data
    hass.config_entries._entries[esphome_entry.entry_id] = esphome_entry
    esphome_entry._async_set_state(hass, ConfigEntryState.LOADED, None)

    # Trigger coordinator update
    coordinator = entry.runtime_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Now should use esphome integration version
    state = hass.states.get("update.test_device_firmware")
    assert state is not None
    assert state.attributes["installed_version"] == esphome_version


async def test_fetch_device_version_no_address(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test _async_fetch_device_version returns early when no address.

    When a device has no address, _async_fetch_device_version should return
    early without attempting to query the device. This tests the defensive
    check by directly calling the method after clearing the address.
    """
    # Create mock dashboard API with device that HAS an address initially
    mock_api = MagicMock()
    mock_api.request = AsyncMock(return_value=None)
    mock_api.get_devices = AsyncMock(
        return_value={
            "configured": [
                {
                    "name": "test_device",
                    "deployed_version": "2023.12.0",
                    "current_version": "2024.5.0",
                    "configuration": "test_device.yaml",
                    "address": "192.168.1.50",
                }
            ]
        }
    )

    # Create esphome_dashboard config entry
    entry = MockConfigEntry(
        title="ESPHome Dashboard",
        domain=DOMAIN,
        data={CONF_URL: "http://192.168.1.100:6052"},
        unique_id="http://192.168.1.100:6052",
    )
    entry.add_to_hass(hass)

    # Mock mDNS port discovery and API client
    mock_device_info = MagicMock()
    mock_device_info.esphome_version = "2024.1.0"

    mock_api_client = MagicMock()
    mock_api_client.connect = AsyncMock()
    mock_api_client.disconnect = AsyncMock()
    mock_api_client.device_info = AsyncMock(return_value=mock_device_info)

    mock_discover_port = AsyncMock(return_value=None)

    with (
        patch(
            "homeassistant.components.esphome_dashboard.ESPHomeDashboardAPI",
            return_value=mock_api,
        ),
        patch(
            "homeassistant.components.esphome_dashboard.update.APIClient",
            return_value=mock_api_client,
        ) as mock_api_client_class,
        patch.object(
            ESPHomeDashboardUpdateEntity,
            "_async_discover_device_port",
            mock_discover_port,
        ),
        patch(
            "homeassistant.components.esphome_dashboard.update.zeroconf.async_get_instance",
            return_value=MagicMock(),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Get the entity
        entity_id = "update.test_device_firmware"
        entity: ESPHomeDashboardUpdateEntity = hass.data["update"].get_entity(entity_id)
        assert entity is not None

        # Reset the mock to track new calls
        mock_api_client_class.reset_mock()

        # Clear the address to test the defensive check in _async_fetch_device_version
        entity._address = None

        # Directly call _async_fetch_device_version - should return early
        await entity._async_fetch_device_version()

        # APIClient should NOT have been called since address is None
        mock_api_client_class.assert_not_called()
