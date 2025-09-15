"""Common fixtures for the Volvo On Call tests."""

import pytest

from homeassistant.components.volvooncall.const import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Volvo On Call",
        data={},
    )
