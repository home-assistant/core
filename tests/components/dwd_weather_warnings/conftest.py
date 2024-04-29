"""Configuration for Deutscher Wetterdienst (DWD) Weather Warnings tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.dwd_weather_warnings.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_dwdwfsapi() -> Generator[MagicMock, None, None]:
    """Return a mocked dwdwfsapi API client."""
    with (
        patch(
            "homeassistant.components.dwd_weather_warnings.coordinator.DwdWeatherWarningsAPI",
            autospec=True,
        ) as mock_api,
        patch(
            "homeassistant.components.dwd_weather_warnings.config_flow.DwdWeatherWarningsAPI",
            new=mock_api,
        ),
    ):
        api = mock_api.return_value
        api.data_valid = False
        api.warncell_id = None
        api.warncell_name = None
        api.last_update = None
        api.current_warning_level = None
        api.current_warnings = None
        api.expected_warning_level = None
        api.expected_warnings = None
        api.update = Mock()
        api.__bool__ = Mock()
        api.__bool__.return_value = True

        yield api
