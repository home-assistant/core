"""Define test fixtures for myuplink."""
from unittest.mock import patch

import pytest

from homeassistant.components.myuplink import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass: HomeAssistant):
    """Define a config entry fixture."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="MyUplink",
        options={},
        entry_id="2ab7896bda8c3875086f1fe6baad4948",
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={"auth_implementation": "myuplink_1", "token": {"expires_at": 123456}},
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the myuplink integration for testing."""
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.myuplink.api.AsyncConfigEntryAuth"), patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
