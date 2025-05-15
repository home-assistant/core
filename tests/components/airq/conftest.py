"""Test fixtures for air-Q."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.airq.const import DOMAIN as AIRQ_DOMAIN
from homeassistant.core import HomeAssistant

from .common import TEST_DEVICE_INFO, TEST_USER_DATA

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.airq.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def airq_config_entry():
    """Create a minimal MockConfigEntry."""
    return MockConfigEntry(
        domain=AIRQ_DOMAIN, data=TEST_USER_DATA, unique_id=TEST_DEVICE_INFO["id"]
    )


@pytest.fixture
def registered_airq_config_entry(hass: HomeAssistant, airq_config_entry):
    """Create & register a minimal MockConfigEntry."""
    airq_config_entry.add_to_hass(hass)
    return airq_config_entry
