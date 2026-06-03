"""Shared pytest fixtures for the Noonlight tests."""

from collections.abc import AsyncGenerator

from httpx import Response
import pytest
import respx

from homeassistant.components.noonlight.const import (
    CONF_API_TOKEN,
    CONF_ENVIRONMENT,
    DOMAIN,
    ENV_SANDBOX,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

# Base URL the sandbox test entry targets (also its unique id).
SANDBOX = "https://api-sandbox.noonlight.com"
STATUS_RE = r".*/dispatch/v1/alarms/.*/status"


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """A sandbox config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Noonlight Sandbox",
        unique_id=SANDBOX,
        data={CONF_API_TOKEN: "test-token", CONF_ENVIRONMENT: ENV_SANDBOX},
    )


@pytest.fixture
async def setup_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> AsyncGenerator[MockConfigEntry]:
    """Add the entry and set it up with the reachability probe mocked (404)."""
    config_entry.add_to_hass(hass)
    with respx.mock:
        respx.get(url__regex=STATUS_RE).mock(return_value=Response(404))
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        yield config_entry
