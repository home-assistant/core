"""Configuration for frontier_silicon tests."""
from unittest.mock import patch

import pytest

from homeassistant.components.frontier_silicon.const import (
    CONF_PIN,
    CONF_WEBFSAPI_URL,
    DOMAIN,
)

from tests.common import MockConfigEntry


@pytest.fixture
def config_entry():
    """Create a mock Frontier Silicon config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="mock_radio_id",
        data={CONF_WEBFSAPI_URL: "http://1.1.1.1:80/webfsapi", CONF_PIN: "1234"},
    )


@pytest.fixture(autouse=True)
def mock_radio_id():
    """Return a valid radio_id."""
    with patch("afsapi.AFSAPI.get_radio_id", return_value="mock_radio_id"):
        yield
