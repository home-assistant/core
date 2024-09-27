"""Test script init."""

from pathlib import Path
from unittest.mock import patch

from homeassistant import scripts


@patch("homeassistant.scripts.get_default_config_dir", return_value=Path("/default"))
def test_config_per_platform(mock_def) -> None:
    """Test config per platform method."""
    assert scripts.get_default_config_dir() == Path("/default")
    assert scripts.extract_config_dir() == Path("/default")
    assert scripts.extract_config_dir([""]) == Path("/default")
    assert scripts.extract_config_dir(["-c", "/arg"]) == Path("/arg")
    assert scripts.extract_config_dir(["--config", "/a"]) == Path("/a")
