"""Tests for TP-Link Omada update entities."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from tplink_omada_client import OmadaControllerStatus, OmadaControllerUpdateInfo
from tplink_omada_client.devices import OmadaListDevice
from tplink_omada_client.exceptions import OmadaClientException, RequestFailed

from homeassistant.components.tplink_omada.const import DOMAIN
from homeassistant.components.tplink_omada.coordinator import (
    POLL_CONTROLLER,
    POLL_DEVICES,
)
from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    DATA_COMPONENT,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
    UpdateEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.update_coordinator import REQUEST_REFRESH_DEFAULT_COOLDOWN

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_array_fixture,
    snapshot_platform,
)
from tests.typing import WebSocketGenerator

POLL_INTERVAL = timedelta(seconds=POLL_DEVICES)
CONTROLLER_POLL_INTERVAL = timedelta(seconds=POLL_CONTROLLER)
REFRESH_COOLDOWN = timedelta(seconds=REQUEST_REFRESH_DEFAULT_COOLDOWN)


async def _rebuild_device_list_with_update(
    hass: HomeAssistant, mac: str, **overrides
) -> list[OmadaListDevice]:
    """Rebuild device list from fixture with specified overrides for a device."""
    devices_data = await async_load_json_array_fixture(
        hass, "devices.json", "tplink_omada"
    )

    for device_data in devices_data:
        if device_data["mac"] == mac:
            device_data.update(overrides)

    return [OmadaListDevice(d) for d in devices_data]


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_omada_client: MagicMock,
) -> MockConfigEntry:
    """Set up the TP-Link Omada integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.tplink_omada.PLATFORMS", [Platform.UPDATE]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry


async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the creation of the TP-Link Omada update entities."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


async def test_firmware_download_in_progress(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_omada_site_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test update entity when firmware download is in progress."""
    entity_id = "update.test_poe_switch_firmware"

    freezer.tick(POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Rebuild device list with fwDownload set to True for the switch
    updated_devices = await _rebuild_device_list_with_update(
        hass, "54-AF-97-00-00-01", fwDownload=True
    )
    mock_omada_site_client.get_devices.return_value = updated_devices

    # Trigger coordinator update
    freezer.tick(POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Verify update entity shows in progress
    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.attributes.get(ATTR_IN_PROGRESS) is True


async def test_install_firmware_success(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_omada_site_client: MagicMock,
) -> None:
    """Test successful firmware installation."""
    entity_id = "update.test_poe_switch_firmware"

    # Verify update is available
    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.state == STATE_ON

    # Call install service
    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify start_firmware_upgrade was called with the correct device
    mock_omada_site_client.start_firmware_upgrade.assert_awaited_once()
    await_args = mock_omada_site_client.start_firmware_upgrade.await_args[0]
    assert await_args[0].mac == "54-AF-97-00-00-01"


async def test_install_controller_firmware_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_omada_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test successful controller firmware installation."""
    entity_id = "update.oc200_test_omada_controller_firmware"
    mock_omada_client.check_firmware_updates.return_value = OmadaControllerUpdateInfo(
        {
            "hardware": {
                "upgrade": True,
                "currentVersion": "1.0.0",
                "latestVersion": "1.0.1",
                "fwReleaseLog": "Fixed things.",
                "releaseUrl": "https://example.com/firmware-release-notes",
                "downloadLink": "https://example.com/firmware.bin",
            }
        }
    )
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.tplink_omada.PLATFORMS", [Platform.UPDATE]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.state == STATE_ON
    assert entity.attributes[ATTR_INSTALLED_VERSION] == "1.0.0"
    assert entity.attributes[ATTR_LATEST_VERSION] == "1.0.1"
    assert entity.attributes[ATTR_SUPPORTED_FEATURES] == (
        UpdateEntityFeature.RELEASE_NOTES | UpdateEntityFeature.INSTALL
    )

    mock_omada_client.check_firmware_updates.reset_mock()

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    freezer.tick(REFRESH_COOLDOWN)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_omada_client.install_controller_firmware.assert_awaited_once_with("1.0.1")
    mock_omada_client.check_firmware_updates.assert_awaited_once()


async def test_controller_update_check_failure_does_not_block_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_omada_client: MagicMock,
) -> None:
    """Test controller update check failures do not block setup."""
    entity_id = "update.oc200_test_omada_controller_firmware"
    mock_omada_client.check_firmware_updates.side_effect = OmadaClientException(
        "Connection error"
    )
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.tplink_omada.PLATFORMS", [Platform.UPDATE]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.state == STATE_UNAVAILABLE


async def test_controller_software_update_installed_version_prefers_status_coordinator(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_omada_client: MagicMock,
) -> None:
    """Test controller software update installed version prefers controller status."""
    entity_id = "update.oc200_test_omada_controller_firmware"
    mock_omada_client.get_controller_status.return_value = OmadaControllerStatus(
        {
            "name": "Test Omada Controller",
            "macAddress": "00-11-22-33-44-55",
            "upTime": 123456,
            "controllerVersion": "6.3.0.45",
            "model": "OC200",
        }
    )
    mock_omada_client.check_firmware_updates.return_value = OmadaControllerUpdateInfo(
        {
            "software": {
                "upgrade": True,
                "currentVersion": "6.2.10.17",
                "latestVersion": "6.3.0.45",
            }
        }
    )
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.tplink_omada.PLATFORMS", [Platform.UPDATE]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.state == STATE_OFF
    assert entity.attributes[ATTR_INSTALLED_VERSION] == "6.3.0.45"
    assert entity.attributes[ATTR_LATEST_VERSION] == "6.3.0.45"


async def test_controller_device_sw_version_updates_with_status_coordinator(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_omada_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test controller device software version updates with controller status."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.tplink_omada.PLATFORMS", [Platform.UPDATE]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "00-11-22-33-44-55"),
        mock_config_entry.entry_id,
    )
    assert device_entry is not None
    assert device_entry.sw_version == "6.2.10.17"

    mock_omada_client.get_controller_status.return_value = OmadaControllerStatus(
        {
            "name": "Test Omada Controller",
            "macAddress": "00-11-22-33-44-55",
            "upTime": 123456,
            "controllerVersion": "6.3.0.45",
            "model": "OC200",
        }
    )

    freezer.tick(CONTROLLER_POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "00-11-22-33-44-55"),
        mock_config_entry.entry_id,
    )
    assert device_entry is not None
    assert device_entry.sw_version == "6.3.0.45"


@pytest.mark.parametrize(
    ("exception_type", "translation_key"),
    [
        (
            RequestFailed(500, "Update rejected"),
            "firmware_update_rejected",
        ),
        (
            OmadaClientException("Connection error"),
            "firmware_update_failed",
        ),
    ],
)
async def test_install_firmware_exceptions(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_omada_site_client: MagicMock,
    exception_type: Exception,
    translation_key: str,
) -> None:
    """Test firmware installation exception handling."""
    entity_id = "update.test_poe_switch_firmware"

    # Mock exception
    mock_omada_site_client.start_firmware_upgrade = AsyncMock(
        side_effect=exception_type
    )

    # Call install service and expect error
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    assert err.value.translation_key == translation_key
    assert err.value.translation_domain == DOMAIN


@pytest.mark.parametrize(
    ("exception_type", "translation_key"),
    [
        (
            RequestFailed(500, "Update rejected"),
            "firmware_update_rejected",
        ),
        (
            OmadaClientException("Connection error"),
            "firmware_update_failed",
        ),
    ],
)
async def test_install_controller_firmware_exceptions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_omada_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    exception_type: Exception,
    translation_key: str,
) -> None:
    """Test controller firmware installation exception handling."""
    entity_id = "update.oc200_test_omada_controller_firmware"
    mock_omada_client.check_firmware_updates.return_value = OmadaControllerUpdateInfo(
        {
            "hardware": {
                "upgrade": True,
                "currentVersion": "1.0.0",
                "latestVersion": "1.0.1",
            }
        }
    )
    mock_omada_client.install_controller_firmware = AsyncMock(
        side_effect=exception_type
    )
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.tplink_omada.PLATFORMS", [Platform.UPDATE]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_omada_client.check_firmware_updates.reset_mock()

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    assert err.value.translation_key == translation_key
    assert err.value.translation_domain == DOMAIN
    freezer.tick(REFRESH_COOLDOWN)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_omada_client.check_firmware_updates.assert_awaited_once()


async def test_install_controller_firmware_rejected_without_hardware(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test controller firmware installation rejects software-only updates."""
    entity = hass.data[DATA_COMPONENT].get_entity(
        "update.oc200_test_omada_controller_firmware"
    )
    assert entity is not None

    with pytest.raises(HomeAssistantError) as err:
        await entity.async_install(version=None, backup=False)

    assert err.value.translation_key == "firmware_update_rejected"
    assert err.value.translation_domain == DOMAIN


@pytest.mark.parametrize(
    ("entity_name", "expected_notes"),
    [
        ("oc200_test_omada_controller", "Release notes for Omada SDN Controller."),
        ("test_router", None),
        ("test_poe_switch", "Bug fixes and performance improvements"),
    ],
)
async def test_release_notes(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    entity_name: str,
    expected_notes: str | None,
) -> None:
    """Test that release notes are available via websocket."""
    entity_id = f"update.{entity_name}_firmware"

    # Get release notes via websocket
    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json(
        {
            "id": 1,
            "type": "update/release_notes",
            "entity_id": entity_id,
        }
    )
    result = await client.receive_json()

    assert expected_notes == result["result"]
