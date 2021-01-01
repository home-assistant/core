"""Test configuration for PS4."""
from unittest.mock import patch

import pytest


@pytest.fixture
def patch_load_json():
    """Prevent load JSON being used."""
    with patch("homeassistant.components.ps4.load_json", return_value={}) as mock_load:
        yield mock_load


@pytest.fixture
def patch_save_json():
    """Prevent save JSON being used."""
    with patch("homeassistant.components.ps4.save_json") as mock_save:
        yield mock_save


@pytest.fixture(autouse=True)
def patch_io(patch_load_json, patch_save_json):
    """Prevent PS4 doing I/O."""
