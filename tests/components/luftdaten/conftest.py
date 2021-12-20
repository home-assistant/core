"""Fixtures for Luftdaten tests."""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.luftdaten import DOMAIN
from homeassistant.components.luftdaten.const import CONF_SENSOR_ID

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="12345",
        domain=DOMAIN,
        data={CONF_SENSOR_ID: 123456},
        unique_id="12345",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.luftdaten.async_setup_entry", return_value=True
    ):
        yield
