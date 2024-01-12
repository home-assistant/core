"""Test System Monitor utils."""

from unittest.mock import Mock, patch

import pytest

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("side_effect", "error_text"),
    [
        (PermissionError("No permission"), "No permission for running user to access"),
        (OSError("OS error"), "was excluded because of: OS error"),
    ],
)
async def test_disk_setup_failure(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: None,
    mock_psutil: Mock,
    mock_os: Mock,
    mock_util: Mock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    error_text: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the disk failures."""

    with patch(
        "homeassistant.components.systemmonitor.util.psutil.disk_usage",
        side_effect=side_effect,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        disk_sensor = hass.states.get("sensor.system_monitor_disk_free_media_share")
        assert disk_sensor is None

        assert error_text in caplog.text
