"""Test fixtures for Generic Cover integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.generic_cover.const import (
    CONF_DURATION,
    CONF_SWITCH_CLOSE,
    CONF_SWITCH_OPEN,
    CONF_TILT_DURATION,
    DOMAIN,
)
from homeassistant.const import CONF_NAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test Generic Cover",
        data={
            CONF_NAME: "Test Generic Cover",
            CONF_SWITCH_OPEN: "switch.test_open",
            CONF_SWITCH_CLOSE: "switch.test_close",
            CONF_DURATION: {"hours": 0, "minutes": 0, "seconds": 10, "milliseconds": 0},
            CONF_TILT_DURATION: {
                "hours": 0,
                "minutes": 0,
                "seconds": 2,
                "milliseconds": 0,
            },
        },
        unique_id="switch.test_open_switch.test_close",
    )


@pytest.fixture
def mock_switch_entities() -> Generator[AsyncMock]:
    """Mock switch entities."""
    with (
        patch("homeassistant.components.switch.is_on", return_value=False),
        patch(
            "homeassistant.core.ServiceRegistry.async_call", new_callable=AsyncMock
        ) as mock_call,
    ):
        yield mock_call
