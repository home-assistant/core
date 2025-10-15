"""Test the Foscam number platform."""

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.foscam.const import DOMAIN
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import setup_mock_foscam_camera
from .const import ENTRY_ID, VALID_CONFIG

from tests.common import MockConfigEntry, snapshot_platform


async def test_number_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test creation of number entities."""
    entry = MockConfigEntry(domain=DOMAIN, data=VALID_CONFIG, entry_id=ENTRY_ID)
    entry.add_to_hass(hass)
    hass.config.internal_url = "http://localhost:8123"
    with (
        # Mock a valid camera instance
        patch("homeassistant.components.foscam.FoscamCamera") as mock_foscam_camera,
        patch("homeassistant.components.foscam.PLATFORMS", [Platform.NUMBER]),
    ):
        setup_mock_foscam_camera(mock_foscam_camera)
        assert await hass.config_entries.async_setup(entry.entry_id)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_setting_number(hass: HomeAssistant) -> None:
    """Test setting a number entity calls the correct method on the camera."""
    entry = MockConfigEntry(domain=DOMAIN, data=VALID_CONFIG, entry_id=ENTRY_ID)
    hass.config.internal_url = "http://localhost:8123"
    entry.add_to_hass(hass)

    with patch("homeassistant.components.foscam.FoscamCamera") as mock_foscam_camera:
        setup_mock_foscam_camera(mock_foscam_camera)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "number.mock_title_device_volume",
                ATTR_VALUE: 42,
            },
            blocking=True,
        )
        mock_foscam_camera.setAudioVolume.assert_called_once_with(42)
