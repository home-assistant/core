"""Common methods for Sense."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from .const import (
    DEVICE_1_DATA,
    DEVICE_1_NAME,
    DEVICE_2_DATA,
    DEVICE_2_NAME,
    MONITOR_ID,
)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.sense.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_sense() -> Generator[MagicMock]:
    """Mock an ASyncSenseable object with a split foundation."""
    with patch("homeassistant.components.sense.ASyncSenseable", autospec=True) as mock:
        gateway = mock.return_value
        gateway._devices = [DEVICE_1_NAME, DEVICE_2_NAME]
        gateway.sense_monitor_id = MONITOR_ID
        gateway.get_monitor_data.return_value = None
        gateway.get_discovered_device_data.return_value = [DEVICE_1_DATA, DEVICE_2_DATA]
        gateway.update_realtime.return_value = None

        def get_realtime():
            yield {"devices": []}
            yield {"devices": [DEVICE_1_DATA]}
            while True:
                yield {"devices": [DEVICE_1_DATA, DEVICE_2_DATA]}

        gateway.get_realtime.side_effect = get_realtime()

        yield gateway
