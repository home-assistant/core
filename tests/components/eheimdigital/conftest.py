"""Configurations for the EHEIM Digital tests."""

import pytest

from homeassistant.components.eheimdigital.const import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
    )
