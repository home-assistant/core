"""Fixtures for Inverse integration tests, adapted from switch_as_x."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_setup_entry(hass: HomeAssistant) -> AsyncMock:  # type: ignore[override]
    """Mock async_setup_entry for inverse to observe config flow completion."""
    with patch(
        "homeassistant.components.inverse.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock
