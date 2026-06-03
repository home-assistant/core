"""Tests fixtures for the Avea integration."""

import pytest

from homeassistant.components.avea.const import DOMAIN
from homeassistant.const import CONF_ADDRESS

from . import AVEA_DISCOVERY_INFO

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock Avea config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Bedroom",
        unique_id=AVEA_DISCOVERY_INFO.address,
        data={CONF_ADDRESS: AVEA_DISCOVERY_INFO.address},
    )
