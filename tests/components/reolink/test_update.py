"""Test the Reolink update platform."""

from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from reolink_aio.exceptions import ReolinkError
from reolink_aio.software_version import NewSoftwareVersion

from homeassistant.components.reolink.update import POLL_AFTER_INSTALL
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN, SERVICE_INSTALL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import TEST_CAM_NAME, TEST_NVR_NAME

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import WebSocketGenerator

TEST_DOWNLOAD_URL = "https://reolink.com/test"
TEST_RELEASE_NOTES = "bugfix 1, bugfix 2"


@pytest.mark.parametrize("entity_name", [TEST_NVR_NAME, TEST_CAM_NAME])
async def test_no_update(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    entity_name: str,
) -> None:
    """Test update state when no update available."""
    reolink_connect.camera_name.return_value = TEST_CAM_NAME

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.UPDATE]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.UPDATE}.{entity_name}_firmware"
    assert hass.states.get(entity_id).state == STATE_OFF


@pytest.mark.parametrize("entity_name", [TEST_NVR_NAME, TEST_CAM_NAME])
async def test_update_str(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    entity_name: str,
) -> None:
    """Test update state when update available with string from API."""
    reolink_connect.camera_name.return_value = TEST_CAM_NAME
    reolink_connect.firmware_update_available.return_value = "New firmware available"

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.UPDATE]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.UPDATE}.{entity_name}_firmware"
    assert hass.states.get(entity_id).state == STATE_ON


@pytest.mark.parametrize("entity_name", [TEST_NVR_NAME, TEST_CAM_NAME])
async def test_update_firm(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    entity_name: str,
) -> None:
    """Test update state when update available with firmware info from reolink.com."""
    reolink_connect.camera_name.return_value = TEST_CAM_NAME
    reolink_connect.camera_sw_version.return_value = "v1.1.0.0.0.0000"
    new_firmware = NewSoftwareVersion(
        version_string="v3.3.0.226_23031644",
        download_url=TEST_DOWNLOAD_URL,
        release_notes=TEST_RELEASE_NOTES,
    )
    reolink_connect.firmware_update_available.return_value = new_firmware

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.UPDATE]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.UPDATE}.{entity_name}_firmware"
    assert hass.states.get(entity_id).state == STATE_ON

    # release notes
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
    assert TEST_DOWNLOAD_URL in result["result"]
    assert TEST_RELEASE_NOTES in result["result"]

    # test install
    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    reolink_connect.update_firmware.assert_called()

    reolink_connect.update_firmware.side_effect = ReolinkError("Test error")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    # test _async_update_future
    reolink_connect.camera_sw_version.return_value = "v3.3.0.226_23031644"
    reolink_connect.firmware_update_available.return_value = False
    freezer.tick(POLL_AFTER_INSTALL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_OFF

    reolink_connect.update_firmware.side_effect = None
