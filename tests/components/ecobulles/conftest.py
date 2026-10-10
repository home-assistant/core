"""Pytest fixtures for Ecobulles tests."""

import pytest

from homeassistant.components.ecobulles.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_EMAIL: "user@example.com",
            CONF_PASSWORD: "secret",
            "eco_ref": "test-eco-ref",
            "name": "Test box",
            "num_serie": "XC240007",
            "firmware_version": "1.0",
        },
        unique_id="test-eco-ref",
    )
