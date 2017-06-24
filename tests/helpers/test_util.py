"""Test helpers util functions."""
import tempfile
import os.path

from homeassistant.helpers.utils import secure_path_check


def test_secure_path_check(hass):
    """Test function for secure_path_check."""
    valid = [
        hass.config.path("output/test.jpg"),
        hass.config.path("output/xy/test.jpg"),
        hass.config.path("www/test.jpg"),
        hass.config.path("www/xy/test.jpg"),
        os.path.join(tempfile.gettempdir, "my_tempfile.jpg"),
    ]

    for path in valid:
        assert secure_path_check(hass, path)

    unvalid = [
        hass.config.path("secure.yaml"),
        hass.config.path("configuration.yaml"),
        "/etc/passwd",
        "/root/secure_file"
    ]

    for path in unvalid:
        assert not secure_path_check(hass, path)
