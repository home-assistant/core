"""Common fixtures for Steam integration."""

import pytest

from homeassistant.components.steam_online.const import DOMAIN

from . import ACCOUNT_1, CONF_DATA, CONF_OPTIONS

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Mock Steam configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA,
        options=CONF_OPTIONS,
        unique_id=ACCOUNT_1,
    )
