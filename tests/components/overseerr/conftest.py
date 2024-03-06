"""Common fixtures for the Overseerr tests."""
from unittest.mock import patch

from overseerr_api.models import RequestCountGet200Response
import pytest

from homeassistant.components.overseerr.const import DEFAULT_URL, DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="12345",
        data={CONF_URL: DEFAULT_URL, CONF_API_KEY: "test-api-key"},
        version=1,
    )


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Fixture for setting up Overseerr integration."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture(autouse=True)
def mock_api_request():
    """Mock an API request."""
    response = RequestCountGet200Response(
        movie=5,
        tv=6,
        approved=7,
        available=8,
        pending=9,
        total=24,
    )
    with patch(
        "homeassistant.components.overseerr.coordinator.RequestApi.request_count_get",
        return_value=response,
    ) as mock_request:
        yield mock_request
