"""Common fixtures for the UniFi Access tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from uiaccessclient import Door

from homeassistant.components.unifi_access.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_async_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.unifi_access.async_setup_entry", return_value=True
    ) as mock_async_setup_entry:
        yield mock_async_setup_entry

    assert len(mock_async_setup_entry.mock_calls) == 1


@pytest.fixture
async def config_entry(
    hass: HomeAssistant, mock_async_setup_entry: AsyncMock
) -> MockConfigEntry:
    """Create config entry for UniFi Access in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.fixture
def mock_doors() -> list[Door]:
    """Return mocked doors."""
    return [
        Door(id="id-1", name="Door 1", is_bind_hub=True),
        Door(id="id-2", name="Door 2", is_bind_hub=True),
        Door(id="bogus", name="Bogus door", is_bind_hub=False),
    ]
