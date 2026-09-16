"""Fixtures for Zentraly tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.zentraly.models import ZentralyDevice


@pytest.fixture
def platform_device() -> MagicMock:
    """Return a connected device for isolated platform behavior tests."""
    device = MagicMock(spec=ZentralyDevice)
    device.device_id = "ZTTIN0100000631"
    device.connected = True
    device.capability_enabled.return_value = True
    device.opentherm_connected = True
    return device


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a Zentraly config entry."""

    with patch(
        "homeassistant.components.zentraly.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup
