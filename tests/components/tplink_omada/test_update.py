"""Tests for TP-Link Omada update entities."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from tplink_omada_client.devices import OmadaListDevice
from tplink_omada_client.exceptions import OmadaClientException, RequestFailed

from homeassistant.components.tplink_omada.coordinator import POLL_DEVICES
from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
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
