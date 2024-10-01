"""Fixtures for Domika integration tests."""

from collections.abc import AsyncIterator, Generator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.domika.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.typing import MockHAClientWebSocket, WebSocketGenerator


@pytest.fixture
async def websocket_client(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> MockHAClientWebSocket:
    """Create a websocket client."""
    return await hass_ws_client(hass)


@asynccontextmanager
async def _cm() -> AsyncIterator[None]:
    yield None


@pytest.fixture
def db_context_manager() -> AbstractAsyncContextManager:
    """Create a websocket client."""
    return _cm()


@pytest.fixture
def database_get_session(db_context_manager) -> Generator[AsyncMock]:
    """Set up the Domika integration for testing."""
    with patch(
        "domika_ha_framework.database.core.get_session",
        return_value=db_context_manager,
    ) as get_session:
        yield get_session


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title=DOMAIN,
        domain=DOMAIN,
        data={},
        options={
            "critical_entities": {
                "smoke_select_all": False,
                "moisture_select_all": False,
                "co_select_all": False,
                "gas_select_all": False,
                "critical_included_entity_ids": [],
            },
        },
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    db_context_manager,
) -> MockConfigEntry:
    """Set up the Domika integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "domika_ha_framework.init",
        return_value=db_context_manager,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry


@pytest.fixture
def mock_ha_event_flow() -> Generator[AsyncMock]:
    """Mock the ha_event.flow."""
    with patch(
        "homeassistant.components.domika.ha_event_flow",
        autospec=True,
    ) as mock_ha_event_flow:
        yield mock_ha_event_flow
