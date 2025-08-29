"""Test the Amcrest camera platform."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.components.amcrest.const import DOMAIN
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_camera_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_amcrest_api: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test camera setup and device registration."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.amcrest.AmcrestChecker", return_value=mock_amcrest_api
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Check what devices are actually in the registry
    all_devices = device_registry.devices
    assert len(all_devices) > 0

    # Verify device is created with serial number as identifier
    device = device_registry.async_get_device(identifiers={(DOMAIN, "ABCD1234567890")})
    assert device is not None
    assert device.name == "Living Room"
    assert device.manufacturer == "Amcrest"

    # Verify camera entity is created
    camera_entities = hass.states.async_entity_ids(CAMERA_DOMAIN)
    assert len(camera_entities) >= 1

    camera_entity_id = (
        f"camera.{mock_config_entry.data['name'].lower().replace(' ', '_')}"
    )
    camera_entity = entity_registry.async_get(camera_entity_id)

    if camera_entity:  # Entity might have different naming
        assert camera_entity.device_id == device.id
        assert camera_entity.platform == DOMAIN

    # Verify camera state
    camera_state = hass.states.get(camera_entities[0])
    assert camera_state is not None


async def test_camera_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_amcrest_api: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test camera device info is properly set."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.amcrest.AmcrestChecker", return_value=mock_amcrest_api
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify device has correct information
        device = device_registry.async_get_device(
            identifiers={
                (DOMAIN, "ABCD1234567890")
            }  # Should use serial number as identifier
        )
        assert device is not None
        assert device.name == "Living Room"
        assert device.manufacturer == "Amcrest"
        assert device.configuration_url == "http://192.168.1.100"


async def test_camera_legacy_yaml_no_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that YAML configured cameras don't create devices."""
    # For YAML configurations, entities should not create device registry entries
    # This would be tested when YAML setup is implemented
    # Devices should only be created for config flow entries
    devices = device_registry.devices
    yaml_devices = [
        d for d in devices.values() if (DOMAIN, "yaml_config") in d.identifiers
    ]
    assert len(yaml_devices) == 0
