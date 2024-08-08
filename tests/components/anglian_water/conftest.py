"""Anglian Water tests configuration."""

import pytest

from homeassistant.components.anglian_water.const import CONF_DEVICE_ID, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry

MOCK_CONFIG_DATA = {
    CONF_USERNAME: "sample@gmail.com",
    CONF_PASSWORD: "sample",
    CONF_DEVICE_ID: "abcdabcd",
}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="sample@gmail.com",
        data=MOCK_CONFIG_DATA,
        unique_id="sample@gmail.com",
    )
