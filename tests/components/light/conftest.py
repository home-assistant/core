"""Light conftest."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.light import Profiles
from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
def mock_light_profiles():
    """Mock loading of profiles."""
    data = {}

    def mock_profiles_class(hass: HomeAssistant) -> Profiles:
        profiles = Profiles(hass)
        profiles.data = data
        profiles.async_initialize = AsyncMock()
        return profiles

    with patch(
        "homeassistant.components.light.Profiles",
        side_effect=mock_profiles_class,
    ):
        yield data
