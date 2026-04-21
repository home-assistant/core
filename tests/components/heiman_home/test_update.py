"""Tests for the Heiman Home update platform."""

from unittest.mock import MagicMock, patch

from heimanconnect import HeimanDevice

from homeassistant.components.heiman_home.const import DOMAIN
from homeassistant.components.heiman_home.update import (
    HeimanUpdateEntity,
    async_setup_entry,
)
from homeassistant.components.update import UpdateEntityFeature
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_update_setup(hass: HomeAssistant, setup_credentials: None) -> None:
    """Test update platform setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED


async def test_update_entity_creation(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test update entity creation from devices."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.manufacturer = "Heiman"
    mock_device.model = "HS1"
    mock_device.product_id = "prod-1"
    mock_device.firmware_version = "1.0.0"
    mock_device.hardware_version = "1.0"
    mock_device.online = True

    mock_coordinator.get_all_devices.return_value = [mock_device]
    mock_coordinator.last_update_success = True
    mock_coordinator.get_device.return_value = mock_device

    added_entities = []

    def async_add_entities(entities):
        added_entities.extend(entities)

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = mock_coordinator

    await async_setup_entry(hass, entry, async_add_entities)
    await hass.async_block_till_done()

    assert len(added_entities) == 1
    update = added_entities[0]
    assert update.unique_id == "device-1_firmware_update"
    assert update.name == "Firmware Info"


async def test_update_entity_available_property(hass: HomeAssistant) -> None:
    """Test update entity available property."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.last_update_success = True
    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    assert update.available is True

    mock_device.online = False
    assert update.available is False

    mock_coordinator.get_device.return_value = None
    assert update.available is False

    mock_device.online = True
    mock_coordinator.get_device.return_value = mock_device
    mock_coordinator.last_update_success = False
    assert update.available is False


async def test_update_entity_installed_version(hass: HomeAssistant) -> None:
    """Test update entity installed_version property."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    assert update.installed_version == "1.0.0"


async def test_update_entity_latest_version(hass: HomeAssistant) -> None:
    """Test update entity latest_version property."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    assert update.latest_version == "1.0.0"


async def test_update_entity_device_info(hass: HomeAssistant) -> None:
    """Test update entity device info."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.manufacturer = "Heiman"
    mock_device.model = "HS1"
    mock_device.product_id = "prod-1"
    mock_device.firmware_version = "1.0.0"
    mock_device.hardware_version = "1.0"
    mock_device.online = True
    mock_device.device_info = None

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    device_info = update.device_info
    assert device_info is not None
    assert device_info["name"] == "Test Device"
    assert device_info["manufacturer"] == "Heiman"
    assert device_info["model"] == "HS1"
    assert device_info["sw_version"] == "1.0.0"
    assert device_info["hw_version"] == "1.0"
    assert (DOMAIN, "device-1") in device_info["identifiers"]


async def test_update_entity_unique_id(hass: HomeAssistant) -> None:
    """Test update entity unique ID."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-123"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    assert update.unique_id == "device-123_firmware_update"


async def test_update_entity_has_entity_name(hass: HomeAssistant) -> None:
    """Test update entity has entity name."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "My Gateway"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    assert update.has_entity_name is True


async def test_update_entity_supported_features(hass: HomeAssistant) -> None:
    """Test update entity supported_features property."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    assert update.supported_features == UpdateEntityFeature.INSTALL | UpdateEntityFeature.SPECIFIC_VERSION


async def test_update_entity_in_progress(hass: HomeAssistant) -> None:
    """Test update entity in_progress property."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"
    mock_device.properties = {}

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    assert update.in_progress is False

    update_prop = MagicMock()
    update_prop.value = "updating"
    mock_device.properties = {"firmware_update_status": update_prop}

    assert update.in_progress is True

    update_prop.value = "downloading"
    assert update.in_progress is True

    update_prop.value = "installing"
    assert update.in_progress is True

    update_prop.value = "idle"
    assert update.in_progress is False


async def test_update_entity_release_summary(hass: HomeAssistant) -> None:
    """Test update entity release_summary property."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    assert update.release_summary is None


async def test_update_entity_title(hass: HomeAssistant) -> None:
    """Test update entity title property."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    assert update.title == "Heiman Firmware"


async def test_update_entity_auto_update(hass: HomeAssistant) -> None:
    """Test update entity auto_update property."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    assert update.auto_update is False


async def test_version_is_newer_with_import_error(hass: HomeAssistant) -> None:
    """Test _version_is_newer handles ImportError."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    # Mock version.parse to raise ImportError
    import importlib
    version_module = importlib.import_module("packaging.version")
    original_parse = version_module.parse

    def mock_parse_raise_import(v):
        raise ImportError("Test ImportError")

    version_module.parse = mock_parse_raise_import
    try:
        # Should fallback to string comparison
        result = update._version_is_newer("2.0.0", "1.0.0")
        assert result is True  # Different versions
    finally:
        version_module.parse = original_parse


async def test_version_is_newer_with_exception(hass: HomeAssistant) -> None:
    """Test _version_is_newer handles generic Exception."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    # Mock version.parse to raise generic Exception
    import importlib
    version_module = importlib.import_module("packaging.version")
    original_parse = version_module.parse

    def mock_parse_raise_exception(v):
        raise ValueError("Test ValueError")

    version_module.parse = mock_parse_raise_exception
    try:
        # Should return False on exception
        result = update._version_is_newer("2.0.0", "1.0.0")
        assert result is False
    finally:
        version_module.parse = original_parse


async def test_update_from_cache_with_unknown_version(hass: HomeAssistant) -> None:
    """Test _update_from_cache updates when installed_version is 'unknown'."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "2.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    # Set installed_version to "unknown"
    update._attr_installed_version = "unknown"

    result = update._update_from_cache()

    assert result is True
    assert update._attr_installed_version == "2.0.0"
    assert update._attr_latest_version == "2.0.0"


async def test_update_from_cache_with_empty_version(hass: HomeAssistant) -> None:
    """Test _update_from_cache does not update when version is empty."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = ""

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    # Keep default (None) version
    result = update._update_from_cache()

    # Should still return True even if no version found
    assert result is True


async def test_update_extract_firmware_version_from_firmware_info_dict(
    hass: HomeAssistant,
) -> None:
    """Test firmware version extraction from firmware_info dict."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = None
    mock_device.raw_data = None
    mock_device.firmware_info = {"version": "4.2.0"}

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    assert update.installed_version == "4.2.0"


async def test_update_extract_firmware_version_firmware_info_no_version(
    hass: HomeAssistant,
) -> None:
    """Test firmware version extraction when firmware_info has no version key."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = None
    mock_device.raw_data = None
    mock_device.firmware_info = {"build": "12345"}  # No 'version' key

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    # Should return None since no version found
    assert update.installed_version is None


async def test_update_latest_version_updates_when_installed_unknown(
    hass: HomeAssistant,
) -> None:
    """Test latest_version updates when installed_version was unknown."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.5.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    # Set installed to unknown initially
    update._attr_installed_version = "unknown"

    result = update._update_from_cache()

    assert result is True
    assert update._attr_installed_version == "1.5.0"
    assert update._attr_latest_version == "1.5.0"


async def test_update_latest_version_does_not_downgrade(hass: HomeAssistant) -> None:
    """Test latest_version does not downgrade if already set."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    # Simulate cached higher version
    update._attr_installed_version = "2.0.0"
    update._attr_latest_version = "2.0.0"

    result = update._update_from_cache()

    assert result is True
    # Should not downgrade
    assert update._attr_installed_version == "2.0.0"


async def test_version_is_newer_with_non_comparable_strings(hass: HomeAssistant) -> None:
    """Test _version_is_newer handles non-comparable version strings."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    # Mock version.parse to raise Exception
    import importlib
    version_module = importlib.import_module("packaging.version")
    original_parse = version_module.parse

    def mock_parse_exception(v):
        raise TypeError("Cannot compare versions")

    version_module.parse = mock_parse_exception
    try:
        result = update._version_is_newer("alpha", "beta")
        assert result is False
    finally:
        version_module.parse = original_parse


async def test_update_extract_firmware_version_from_attribute(hass: HomeAssistant) -> None:
    """Test firmware version extraction from device.firmware_version attribute."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "2.5.1"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    assert update.installed_version == "2.5.1"


async def test_update_extract_firmware_version_from_raw_data(hass: HomeAssistant) -> None:
    """Test firmware version extraction from raw_data.firmwareInfo.version."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = None
    mock_device.raw_data = {
        "firmwareInfo": {
            "version": "3.0.0",
        }
    }

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    assert update.installed_version == "3.0.0"


async def test_update_extract_firmware_version_from_firmware_info(
    hass: HomeAssistant,
) -> None:
    """Test firmware version extraction from firmware_info.version."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = None
    mock_device.raw_data = None
    mock_device.firmware_info = {
        "version": "4.0.0",
    }

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    assert update.installed_version == "4.0.0"


async def test_update_extract_firmware_version_not_found(hass: HomeAssistant) -> None:
    """Test firmware version extraction when not found."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = None
    mock_device.raw_data = None
    mock_device.firmware_info = None

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    assert update.installed_version is None


async def test_update_entity_async_update(hass: HomeAssistant) -> None:
    """Test update entity async_update method."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    await update.async_update()

    assert update.installed_version == "1.0.0"


async def test_update_entity_handle_coordinator_update(hass: HomeAssistant) -> None:
    """Test update entity _handle_coordinator_update method."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    # Mock async_write_ha_state since entity is not added to hass
    update.async_write_ha_state = MagicMock()

    # _handle_coordinator_update should call _update_from_cache
    update._handle_coordinator_update()

    assert update.installed_version == "1.0.0"
    # Verify async_write_ha_state was called
    update.async_write_ha_state.assert_called_once()


async def test_update_version_is_newer(hass: HomeAssistant) -> None:
    """Test _version_is_newer method."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    assert update._version_is_newer("2.0.0", "1.0.0") is True
    assert update._version_is_newer("1.1.0", "1.0.0") is True
    assert update._version_is_newer("1.0.1", "1.0.0") is True
    assert update._version_is_newer("1.0.0", "1.0.0") is False
    assert update._version_is_newer("1.0.0", "2.0.0") is False


async def test_update_version_is_newer_equal(hass: HomeAssistant) -> None:
    """Test _version_is_newer method with equal versions."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    assert update._version_is_newer("1.0.0", "1.0.0") is False


async def test_update_version_is_newer_older(hass: HomeAssistant) -> None:
    """Test _version_is_newer method with older version."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    assert update._version_is_newer("0.9.0", "1.0.0") is False


async def test_update_entity_deduplication(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test update entity deduplication within a single call."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.manufacturer = "Heiman"
    mock_device.model = "HS1"
    mock_device.product_id = "prod-1"
    mock_device.firmware_version = "1.0.0"
    mock_device.hardware_version = "1.0"
    mock_device.online = True

    mock_coordinator.get_all_devices.return_value = [mock_device]
    mock_coordinator.last_update_success = True
    mock_coordinator.get_device.return_value = mock_device

    added_entities = []

    def async_add_entities(entities):
        added_entities.extend(entities)

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = mock_coordinator

    await async_setup_entry(hass, entry, async_add_entities)
    await hass.async_block_till_done()

    # Verify entities are created (within a single call, deduplication happens)
    assert len(added_entities) == 1
    assert added_entities[0].unique_id == "device-1_firmware_update"


async def test_update_creation_with_multiple_devices(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test update entity creation with multiple devices."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    mock_device1 = MagicMock(spec=HeimanDevice)
    mock_device1.device_id = "device-1"
    mock_device1.device_name = "Test Device 1"
    mock_device1.manufacturer = "Heiman"
    mock_device1.model = "HS1"
    mock_device1.product_id = "prod-1"
    mock_device1.firmware_version = "1.0.0"
    mock_device1.hardware_version = "1.0"
    mock_device1.online = True

    mock_device2 = MagicMock(spec=HeimanDevice)
    mock_device2.device_id = "device-2"
    mock_device2.device_name = "Test Device 2"
    mock_device2.manufacturer = "Heiman"
    mock_device2.model = "HS2"
    mock_device2.product_id = "prod-2"
    mock_device2.firmware_version = "2.0.0"
    mock_device2.hardware_version = "1.0"
    mock_device2.online = True

    mock_coordinator.get_all_devices.return_value = [mock_device1, mock_device2]
    mock_coordinator.last_update_success = True
    mock_coordinator.get_device.return_value = mock_device1

    added_entities = []

    def async_add_entities(entities):
        added_entities.extend(entities)

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = mock_coordinator

    await async_setup_entry(hass, entry, async_add_entities)
    await hass.async_block_till_done()

    assert len(added_entities) == 2
    unique_ids = {update.unique_id for update in added_entities}
    assert "device-1_firmware_update" in unique_ids
    assert "device-2_firmware_update" in unique_ids


async def test_update_installed_version_no_version(hass: HomeAssistant) -> None:
    """Test installed_version when no firmware version is available."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = None
    mock_device.raw_data = None
    mock_device.firmware_info = None

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    assert update.installed_version is None


async def test_update_latest_version_fallback(hass: HomeAssistant) -> None:
    """Test latest_version fallback to installed_version."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    assert update.latest_version == "1.0.0"


async def test_update_installed_version_device_not_found(hass: HomeAssistant) -> None:
    """Test installed_version returns None when device not found and no cache."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = None  # Explicitly set to None

    # Device not found in coordinator
    mock_coordinator.get_device.return_value = None

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    # Both cached version and dynamic fetch return None
    assert update.installed_version is None


async def test_update_from_cache_device_not_found(hass: HomeAssistant) -> None:
    """Test _update_from_cache returns False when device not found."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    # Device not found in coordinator
    mock_coordinator.get_device.return_value = None

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    result = update._update_from_cache()
    assert result is False


async def test_update_from_cache_sets_versions(hass: HomeAssistant) -> None:
    """Test _update_from_cache sets installed and latest version."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "2.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    # Version should be set during __init__ via _update_from_cache
    assert update.installed_version == "2.0.0"
    assert update.latest_version == "2.0.0"


async def test_version_is_newer_with_comparison(hass: HomeAssistant) -> None:
    """Test _version_is_newer with packaging module."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    # Test version comparison using packaging module
    assert update._version_is_newer("2.0.0", "1.0.0") is True
    assert update._version_is_newer("1.5.0", "1.0.0") is True
    assert update._version_is_newer("1.0.1", "1.0.0") is True
    assert update._version_is_newer("1.0.0", "1.0.0") is False
    assert update._version_is_newer("0.9.0", "1.0.0") is False


async def test_update_latest_version_fallback_installed(hass: HomeAssistant) -> None:
    """Test latest_version fallback to installed_version."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    # latest_version should fallback to installed_version
    assert update.latest_version == "1.0.0"


async def test_update_in_progress_no_update(hass: HomeAssistant) -> None:
    """Test in_progress property when no update is happening."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"
    mock_device.properties = {}

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    # No update property means in_progress is False
    assert update.in_progress is False


async def test_update_latest_version_fallback_to_installed(hass: HomeAssistant) -> None:
    """Test latest_version falls back to installed_version when not set."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.5.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    # latest_version should be set to installed_version during __init__
    # (the _update_from_cache method sets _attr_latest_version)
    assert update._attr_latest_version == "1.5.0"
    assert update.latest_version == "1.5.0"


async def test_update_latest_version_set_to_installed_when_empty(hass: HomeAssistant) -> None:
    """Test _update_from_cache sets latest_version when it's empty."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "2.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    # latest_version should be set to installed_version
    assert update._attr_latest_version == "2.0.0"
    assert update.latest_version == "2.0.0"


async def test_update_installed_version_not_updated_when_cached(hass: HomeAssistant) -> None:
    """Test _update_from_cache does not update installed_version when already set."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    # Pre-set a higher version
    update._attr_installed_version = "2.0.0"
    update._attr_latest_version = "2.0.0"

    # Call _update_from_cache should not downgrade
    result = update._update_from_cache()

    assert result is True
    # Should not downgrade
    assert update._attr_installed_version == "2.0.0"
    assert update._attr_latest_version == "2.0.0"


async def test_update_available_with_no_latest_version(hass: HomeAssistant) -> None:
    """Test update entity available when latest_version is None."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    # latest_version property should still work when _attr_latest_version is None
    assert update.latest_version == "1.0.0"
    # No update available (versions are the same)
    assert update._version_is_newer(update.latest_version, update.installed_version) is False


async def test_version_is_newer_with_logging(hass: HomeAssistant) -> None:
    """Test _version_is_newer logs exception and returns False."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    # Mock version.parse to raise InvalidVersion which is a subclass of Exception
    import importlib
    from packaging.version import InvalidVersion

    version_module = importlib.import_module("packaging.version")
    original_parse = version_module.parse

    def mock_parse_invalid(v):
        raise InvalidVersion(f"Invalid version: {v}")

    version_module.parse = mock_parse_invalid
    try:
        # Should log exception and return False
        result = update._version_is_newer("invalid-version", "1.0.0")
        assert result is False
    finally:
        version_module.parse = original_parse


async def test_version_is_newer_generic_exception(hass: HomeAssistant) -> None:
    """Test _version_is_newer handles generic Exception with logging."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    # Mock version.parse to raise generic Exception
    import importlib

    version_module = importlib.import_module("packaging.version")
    original_parse = version_module.parse

    def mock_parse_exception(v):
        raise RuntimeError("Unexpected error")

    version_module.parse = mock_parse_exception
    try:
        # Should return False on generic exception
        result = update._version_is_newer("2.0.0", "1.0.0")
        assert result is False
    finally:
        version_module.parse = original_parse


async def test_update_extract_firmware_version_firmware_info_not_dict(
    hass: HomeAssistant,
) -> None:
    """Test firmware version extraction when firmware_info is not a dict."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = None
    mock_device.raw_data = None
    # firmware_info is not a dict but a string or other type
    mock_device.firmware_info = "not-a-dict"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    # Should return None since firmware_info is not a dict
    assert update.installed_version is None


async def test_update_extract_firmware_version_raw_data_with_non_dict_firmwareinfo(
    hass: HomeAssistant,
) -> None:
    """Test firmware version extraction when firmwareInfo in raw_data is not a dict."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = None
    # raw_data has firmwareInfo that is not a dict (e.g., string)
    mock_device.raw_data = {"firmwareInfo": "not-a-dict"}
    mock_device.firmware_info = None

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    # Should return None since firmwareInfo is not a dict
    assert update.installed_version is None


async def test_update_latest_version_returns_installed_when_no_attr(
    hass: HomeAssistant,
) -> None:
    """Test latest_version returns installed_version when _attr_latest_version is falsy."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    # Simulate _attr_latest_version being set to empty string
    update._attr_latest_version = ""
    update._attr_installed_version = "1.0.0"

    # latest_version should return installed_version when _attr_latest_version is falsy
    assert update.latest_version == "1.0.0"


async def test_update_installed_version_returns_device_version(
    hass: HomeAssistant,
) -> None:
    """Test installed_version returns device firmware version when no cached value."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "2.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    # installed_version should return device firmware version
    assert update.installed_version == "2.0.0"


async def test_update_in_progress_with_variant_case(hass: HomeAssistant) -> None:
    """Test in_progress with uppercase variant values."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    update_prop = MagicMock()
    # Test uppercase variant
    update_prop.value = "UPDATING"
    mock_device.properties = {"firmware_update_status": update_prop}

    # Should match "updating" regardless of case
    assert update.in_progress is True


async def test_update_in_progress_no_value(hass: HomeAssistant) -> None:
    """Test in_progress when property value is falsy."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    update_prop = MagicMock()
    update_prop.value = None
    mock_device.properties = {"firmware_update_status": update_prop}

    assert update.in_progress is False


async def test_update_in_progress_empty_string(hass: HomeAssistant) -> None:
    """Test in_progress when property value is empty string."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    update_prop = MagicMock()
    update_prop.value = ""
    mock_device.properties = {"firmware_update_status": update_prop}

    assert update.in_progress is False


async def test_version_is_newer_prerelease_versions(hass: HomeAssistant) -> None:
    """Test _version_is_newer with prerelease versions."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    # Test prerelease comparison
    assert update._version_is_newer("2.0.0-beta", "1.0.0") is True
    assert update._version_is_newer("1.0.0-alpha", "1.0.0-beta") is False


async def test_update_in_progress_with_other_variant_case(hass: HomeAssistant) -> None:
    """Test in_progress with different case variations."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    # Test uppercase DOWNLOADING
    update_prop = MagicMock()
    update_prop.value = "DOWNLOADING"
    mock_device.properties = {"firmware_update_status": update_prop}
    assert update.in_progress is True

    # Test mixed case INSTALLING
    update_prop.value = "InStAlLiNg"
    assert update.in_progress is True


async def test_update_version_is_newer_with_oserror(hass: HomeAssistant) -> None:
    """Test _version_is_newer handles OSError."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "1.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    # Mock version.parse to raise OSError
    import importlib

    version_module = importlib.import_module("packaging.version")
    original_parse = version_module.parse

    def mock_parse_oserror(v):
        raise OSError("Test OSError")

    version_module.parse = mock_parse_oserror
    try:
        result = update._version_is_newer("2.0.0", "1.0.0")
        assert result is False
    finally:
        version_module.parse = original_parse


async def test_update_from_cache_sets_latest_when_empty(hass: HomeAssistant) -> None:
    """Test _update_from_cache sets latest_version when _attr_latest_version is empty."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.firmware_version = "2.0.0"

    mock_coordinator.get_device.return_value = mock_device

    update = HeimanUpdateEntity(
        coordinator=mock_coordinator,
        device=mock_device,
    )

    # Manually set _attr_latest_version to empty/None to trigger the condition
    update._attr_latest_version = None
    update._attr_installed_version = "1.0.0"

    # Call _update_from_cache
    result = update._update_from_cache()

    assert result is True
    # latest_version should be set to installed_version since _attr_latest_version was None
    assert update._attr_latest_version == "2.0.0"
