"""Fixtures for the Code Mode tests."""

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.code_mode.const import DOMAIN


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a Code Mode config entry."""
    return MockConfigEntry(domain=DOMAIN, title="Code Mode")
