"""Configure tests for the Onkyo integration."""

import pytest

from homeassistant.components.onkyo.const import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Create Onkyo entry in Home Assistant."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Onkyo",
        data={},
    )
