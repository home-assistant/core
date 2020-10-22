"""Light conftest."""

import pytest

from homeassistant.components.light import Profiles

from tests.async_mock import patch


@pytest.fixture(autouse=True)
def mock_profiles():
    """Mock loading of profiles."""
    data = {}

    def mock_profiles_class(hass):
        profiles = Profiles(hass)
        profiles.data = data
        return profiles

    with patch(
        "homeassistant.components.light.Profiles", side_effect=mock_profiles_class
    ):
        yield data
