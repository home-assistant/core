"""Fixtures for the solax integration tests."""

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.solax.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock solax config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "192.168.1.87",
            CONF_PORT: 80,
            CONF_PASSWORD: "password",
        },
        unique_id="ABCDEFGHIJ",
    )
