"""Common test fixtures."""

from collections.abc import AsyncIterator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.syncthing.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import MOCK_ENTRY, SERVER_ID, create_mock_syncthing_client

from tests.common import MockConfigEntry


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock ConfigEntry for Syncthing component."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_ENTRY,
        unique_id=SERVER_ID,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_syncthing_client() -> MagicMock:
    """Create a mock Syncthing client."""
    return create_mock_syncthing_client()


@pytest.fixture
async def mock_syncthing(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing_client: MagicMock,
) -> AsyncIterator[MagicMock]:
    """Create a mock Syncthing client and set up the config entry."""
    with (
        patch(
            "homeassistant.components.syncthing.aiosyncthing.Syncthing",
            autospec=True,
        ) as mock_class,
        patch(
            "homeassistant.components.syncthing.config_flow.aiosyncthing.Syncthing",
            new=mock_class,
        ),
    ):
        mock_class.return_value = mock_syncthing_client
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield mock_syncthing_client
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
