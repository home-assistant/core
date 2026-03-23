"""Fixtures for the Touchline config flow tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_pytouchline() -> MagicMock:
    """Patch PyTouchline used by the config flow."""
    with patch("homeassistant.components.touchline.config_flow.PyTouchline") as cls:
        instance = cls.return_value
        instance.get_number_of_devices.return_value = 1
        instance.update.return_value = None
        instance.get_controller_id.return_value = "controller-1"
        yield instance


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.touchline.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
