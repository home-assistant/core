"""Light conftest."""

import pytest

from homeassistant.components import light

from tests.async_mock import patch

orig_load_profiles = light.Profiles.load_profiles


@pytest.fixture(autouse=True)
def mock_profile_loading():
    """Mock loading of profiles."""

    async def fake_load(hass):
        hass.data[light.DATA_PROFILES] = {}
        return True

    with patch(
        "homeassistant.components.light.Profiles.load_profiles", side_effect=fake_load
    ) as mock_load_profiles:
        yield mock_load_profiles


@pytest.fixture()
def not_mock_profile_loading(mock_profile_loading):
    """Do not mock the profile loading."""
    mock_profile_loading.side_effect = orig_load_profiles
