"""Fixtures for Discovergy integration tests."""
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.discovergy import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.discovergy.const import GET_METERS


@pytest.fixture
def mock_meters() -> Mock:
    """Patch libraries."""
    with patch("pydiscovergy.Discovergy.meters") as discovergy:
        discovergy.side_effect = AsyncMock(return_value=GET_METERS)
        yield discovergy


@pytest.fixture
async def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a MockConfigEntry for testing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="user@example.org",
        unique_id="user@example.org",
        data={CONF_EMAIL: "user@example.org", CONF_PASSWORD: "supersecretpassword"},
    )
    entry.add_to_hass(hass)

    return entry
