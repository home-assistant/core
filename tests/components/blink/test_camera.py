"""Test the Blink camera platform."""

import errno
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.blink.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


@pytest.mark.parametrize(
    ("service_name", "api_method", "path_field"),
    [
        pytest.param(
            "save_recent_clips",
            "save_recent_clips",
            "file_path",
            id="save_recent_clips",
        ),
        pytest.param("save_video", "video_to_file", "filename", id="save_video"),
    ],
)
@pytest.mark.parametrize(
    ("error_no", "translation_key"),
    [
        (errno.EACCES, "os_write_permission_denied"),
        (errno.ENOSPC, "os_write_no_space"),
        (errno.EROFS, "os_write_read_only"),
        (errno.ENOENT, "os_write_dir_not_found"),
        (errno.EIO, "os_write_error"),
    ],
)
async def test_write_error_raises_translated_error(
    hass: HomeAssistant,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    camera: MagicMock,
    tmp_path: Path,
    service_name: str,
    api_method: str,
    path_field: str,
    error_no: int,
    translation_key: str,
) -> None:
    """Test that an OSError while saving raises a translated write error."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    hass.config.allowlist_external_dirs = {tmp_path}
    getattr(camera, api_method).side_effect = OSError(error_no, "error")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            service_name,
            {ATTR_ENTITY_ID: "camera.camera_1", path_field: str(tmp_path)},
            blocking=True,
        )

    assert exc_info.value.translation_domain == "homeassistant"
    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders == {"path": str(tmp_path)}
