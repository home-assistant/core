"""Test the Blink camera platform."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from homeassistant.components.blink.camera import BlinkCamera
from homeassistant.components.blink.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("entity_method", "api_method"),
    [
        pytest.param("save_recent_clips", "save_recent_clips", id="save_recent_clips"),
        pytest.param("save_video", "video_to_file", id="save_video"),
    ],
)
async def test_cant_write_raises_service_validation_error(
    hass: HomeAssistant,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    camera: MagicMock,
    tmp_path: Path,
    entity_method: str,
    api_method: str,
) -> None:
    """Test that OSError raises ServiceValidationError with the error as placeholder."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    hass.config.allowlist_external_dirs = {tmp_path}
    getattr(camera, api_method).side_effect = OSError("disk full")

    coordinator = mock_config_entry.runtime_data
    camera_entity = BlinkCamera(coordinator, camera.name, camera)
    camera_entity.hass = hass

    with pytest.raises(ServiceValidationError) as exc_info:
        await getattr(camera_entity, entity_method)(str(tmp_path))

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "cant_write"
    assert exc_info.value.translation_placeholders == {"error": "disk full"}
