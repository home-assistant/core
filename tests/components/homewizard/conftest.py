"""Fixtures for HomeWizard integration tests."""
import pytest

from homeassistant.components.homewizard.const import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry_data():
    """Return the default mocked config entry data."""
    return {
        "product_name": "Product Name",
        "product_type": "product_type",
        "serial": "aabbccddeeff",
        "name": "Product Name",
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
