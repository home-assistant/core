"""Common fixtures for the LoRaWAN tests."""
from collections.abc import Generator
import logging
from unittest.mock import AsyncMock, patch

import pytest

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry():
    """Mock LoRaWAN config entry."""
    config_entry = MockConfigEntry(
        domain="lorawan",
        title="TEST-ENTRY-TITLE",
        data={
            "manufacturer": "browan",
            "model": "TBMS100",
        },
        unique_id="0011223344556677",
        version=3,
    )
    return config_entry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.lorawan.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def set_caplog_debug(
    caplog: pytest.LogCaptureFixture,
):
    """Disable all loggers except the DUT set to all messages."""
    caplog.set_level(level=logging.CRITICAL + 1)
    caplog.set_level(level=logging.DEBUG, logger="homeassistant.components.lorawan")
    caplog.set_level(
        level=logging.DEBUG, logger="homeassistant.components.lorawan.config_flow"
    )
    caplog.set_level(
        level=logging.DEBUG, logger="homeassistant.components.lorawan.sensor"
    )
    return caplog
