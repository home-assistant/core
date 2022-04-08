"""Fixtures for HomeWizard integration tests."""
import pytest

from homeassistant.components.homewizard.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry_data():
    """Return the default mocked config entry data."""
    return {
        "product_name": "Product Name",
        "product_type": "product_type",
        "serial": "aabbccddeeff",
        "name": "Product Name",
        CONF_IP_ADDRESS: "1.2.3.4",
    }


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Product Name (aabbccddeeff)",
        domain=DOMAIN,
        data={},
        unique_id="aabbccddeeff",
    )
