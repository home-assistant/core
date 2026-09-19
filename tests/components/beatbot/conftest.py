"""Test fixtures for the Beatbot integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent config-flow tests from setting up the integration."""
    with patch(
        "homeassistant.components.beatbot.async_setup_entry", return_value=True
    ) as setup_entry:
        yield setup_entry


@pytest.fixture
def mock_get_devices() -> Generator[AsyncMock]:
    """Mock the resource API check performed during configuration."""
    with patch(
        "homeassistant.components.beatbot.config_flow.BeatbotClient.get_devices",
        return_value=[],
    ) as get_devices:
        yield get_devices
