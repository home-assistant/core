"""Test script init."""
from unittest.mock import patch

import homeassistant.scripts as scripts


@patch("homeassistant.scripts.get_default_config_dir", return_value="/default")
def test_config_per_platform(mock_def) -> None:
    """Test config per platform method."""
    assert scripts.get_default_config_dir() == "/default"
    assert scripts.extract_config_dir() == "/default"
    assert scripts.extract_config_dir([""]) == "/default"
    assert scripts.extract_config_dir(["-c", "/arg"]) == "/arg"
    assert scripts.extract_config_dir(["--config", "/a"]) == "/a"
