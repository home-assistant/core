"""Test script init."""
import homeassistant.scripts as scripts

from tests.async_mock import patch


@patch("homeassistant.scripts.get_default_config_dir", return_value="/default")
def test_config_per_platform(mock_def):
    """Test config per platform method."""
    assert scripts.get_default_config_dir() == "/default"
    assert scripts.extract_config_dir() == "/default"
    assert scripts.extract_config_dir([""]) == "/default"
    assert scripts.extract_config_dir(["-c", "/arg"]) == "/arg"
    assert scripts.extract_config_dir(["--config", "/a"]) == "/a"
