"""Tests for the legacy device tracker component."""
from unittest.mock import mock_open, patch

from homeassistant.components.device_tracker import legacy
from homeassistant.core import HomeAssistant
from homeassistant.util.yaml import dump

from tests.common import patch_yaml_files


def test_remove_device_from_config(hass: HomeAssistant):
    """Test the removal of a device from a config."""
    yaml_devices = {
        "test": {
            "hide_if_away": True,
            "mac": "00:11:22:33:44:55",
            "name": "Test name",
            "picture": "/local/test.png",
            "track": True,
        },
        "test2": {
            "hide_if_away": True,
            "mac": "00:ab:cd:33:44:55",
            "name": "Test2",
            "picture": "/local/test2.png",
            "track": True,
        },
    }
    mopen = mock_open()

    files = {legacy.YAML_DEVICES: dump(yaml_devices)}
    with patch_yaml_files(files, True), patch(
        "homeassistant.components.device_tracker.legacy.open", mopen
    ):
        legacy.remove_device_from_config(hass, "test")

    mopen().write.assert_called_once_with(
        "test2:\n"
        "  hide_if_away: true\n"
        "  mac: 00:ab:cd:33:44:55\n"
        "  name: Test2\n"
        "  picture: /local/test2.png\n"
        "  track: true\n"
    )
