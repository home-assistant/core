"""Fixtures for the London Air integration tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.london_air.const import CONF_LOCATIONS, DOMAIN

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="London Air",
        unique_id=DOMAIN,
        data={CONF_LOCATIONS: ["Merton"]},
    )


@pytest.fixture
def api_payload() -> dict[str, Any]:
    """Return the API fixture payload."""
    return load_json_object_fixture("london_air.json", DOMAIN)


@pytest.fixture
def mock_session() -> Generator[AsyncMock]:
    """Mock the aiohttp client session used by the integration."""
    session = AsyncMock()
    with (
        patch(
            "homeassistant.components.london_air.coordinator.async_get_clientsession",
            return_value=session,
        ),
        patch(
            "homeassistant.components.london_air.config_flow.async_get_clientsession",
            return_value=session,
        ),
    ):
        yield session
