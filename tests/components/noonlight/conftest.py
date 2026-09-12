"""Shared pytest fixtures for the Noonlight tests."""

from collections.abc import AsyncGenerator

from httpx import Response
import pytest
import respx

from homeassistant.components.noonlight.const import DOMAIN
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

STATUS_RE = r".*/dispatch/v1/alarms/.*/status"


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """A Noonlight config entry (single instance)."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Noonlight",
        data={CONF_API_TOKEN: "test-token"},
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
