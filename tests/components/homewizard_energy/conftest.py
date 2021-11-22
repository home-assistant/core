"""Fixtures for HomeWizard integration tests."""
import pytest

from homeassistant.components.homewizard_energy.const import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry_data():
    """Return the default mocked config entry data."""
    return {
        "custom_name": "Custom Name",
        "unique_id": "aabbccddeeff",
    }


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="HomeWizard Energy",
        domain=DOMAIN,
        data={},
        unique_id="aabbccddeeff",
    )
