"""Tests for TP-Link Omada update entities."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from tplink_omada_client.definitions import OmadaControllerUpdateInfo
from tplink_omada_client.devices import OmadaListDevice
from tplink_omada_client.exceptions import OmadaClientException, RequestFailed

from homeassistant.components.tplink_omada.coordinator import POLL_DEVICES
from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
    UpdateEntityFeature,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_array_fixture,
    snapshot_platform,
)
from tests.typing import WebSocketGenerator

POLL_INTERVAL = timedelta(seconds=POLL_DEVICES)


def _controller_update_info(
    *,
    hardware_upgrade: bool = False,
    software_upgrade: bool = False,
) -> OmadaControllerUpdateInfo:
    """Return mocked controller update information."""
    return OmadaControllerUpdateInfo(
        {
            "hardware": {
                "upgrade": hardware_upgrade,
                "currentVersion": "6.2.10.17",
                "latestVersion": ("6.2.11.1" if hardware_upgrade else "6.2.10.17"),
                "fwReleaseLog": "Controller hardware update",
            },
            "software": {
                "upgrade": software_upgrade,
                "currentVersion": "6.2.10.17",
                "latestVersion": ("6.2.12.1" if software_upgrade else "6.2.10.17"),
                "releaseLog": "Controller software update",
            },
        }
    )


async def _async_setup_update_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Set up only the TP-Link Omada update platform."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.tplink_omada.PLATFORMS", [Platform.UPDATE]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


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


@pytest.mark.parametrize(
    ("exception_type", "error_message"),
    [
        (
            RequestFailed(500, "Update rejected"),
            "Firmware update request rejected",
        ),
        (
            OmadaClientException("Connection error"),
            "Unable to send Firmware update request. Check the controller is online.",
        ),
    ],
)
async def test_install_firmware_exceptions(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_omada_site_client: MagicMock,
    exception_type: Exception,
    error_message: str,
) -> None:
    """Test firmware installation exception handling."""
    entity_id = "update.test_poe_switch_firmware"

    # Mock exception
    mock_omada_site_client.start_firmware_upgrade = AsyncMock(
        side_effect=exception_type
    )

    # Call install service and expect error
    with pytest.raises(
        HomeAssistantError,
        match=error_message,
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("entity_name", "expected_notes"),
    [
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


async def test_controller_hardware_update_install_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_omada_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test successful controller hardware firmware installation."""
    mock_omada_client.check_firmware_updates.return_value = _controller_update_info(
        hardware_upgrade=True
    )
    mock_omada_client.upgrade_controller_firmware = AsyncMock()

    await _async_setup_update_platform(hass, mock_config_entry)

    entity_id = "update.oc200_firmware"
    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.state == STATE_ON

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.supported_features == (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.RELEASE_NOTES
    )

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_omada_client.upgrade_controller_firmware.assert_awaited_once_with("6.2.11.1")


@pytest.mark.parametrize(
    ("exception_type", "error_message"),
    [
        (
            RequestFailed(500, "Update rejected"),
            "Controller firmware update request rejected",
        ),
        (
            OmadaClientException("Connection error"),
            "Unable to send controller firmware update request. Check the controller is online.",
        ),
    ],
)
async def test_controller_hardware_update_install_exceptions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_omada_client: MagicMock,
    exception_type: Exception,
    error_message: str,
) -> None:
    """Test controller hardware firmware installation exception handling."""
    mock_omada_client.check_firmware_updates.return_value = _controller_update_info(
        hardware_upgrade=True
    )
    mock_omada_client.upgrade_controller_firmware = AsyncMock(
        side_effect=exception_type
    )

    await _async_setup_update_platform(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError, match=error_message):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.oc200_firmware"},
            blocking=True,
        )


async def test_controller_software_update_does_not_support_install(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_omada_client: MagicMock,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test controller software updates expose version info without install support."""
    mock_omada_client.check_firmware_updates.return_value = _controller_update_info(
        software_upgrade=True
    )

    await _async_setup_update_platform(hass, mock_config_entry)

    entity_id = "update.oc200_firmware"
    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.state == STATE_ON
    assert entity.attributes["installed_version"] == "6.2.10.17"
    assert entity.attributes["latest_version"] == "6.2.12.1"

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.supported_features == UpdateEntityFeature.RELEASE_NOTES

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "update/release_notes",
            "entity_id": entity_id,
        }
    )
    result = await client.receive_json()

    assert result["result"] == "Controller software update"
