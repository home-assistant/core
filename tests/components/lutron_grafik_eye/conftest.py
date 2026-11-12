"""Fixtures for the Lutron GRAFIK Eye tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_client() -> Generator[MagicMock]:
    """Mock the GRAFIK Eye client."""
    with patch(
        "homeassistant.components.lutron_grafik_eye.config_flow.GrafikEyeClient",
        autospec=True,
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[MagicMock]:
    """Prevent the integration from setting up."""
    with patch(
        "homeassistant.components.lutron_grafik_eye.async_setup_entry",
        return_value=None,
    ) as mock:
        yield mock
