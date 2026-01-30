"""Test the ESPHome Dashboard update platform."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.esphome_dashboard.const import DOMAIN
from homeassistant.components.esphome_dashboard.update import (
    ESPHomeDashboardUpdateEntity,
)
from homeassistant.components.update import SERVICE_INSTALL
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

    with patch(
        "homeassistant.components.esphome_dashboard.ESPHomeDashboardAPI",
        return_value=mock_api,
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
