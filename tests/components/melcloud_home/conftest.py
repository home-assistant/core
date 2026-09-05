"""Common fixtures for the MELCloud Home tests."""

import asyncio
from collections.abc import AsyncIterator, Generator
from unittest.mock import AsyncMock, patch

from aiomelcloudhome import (
    MELCloudHome,
    MELCloudHomeWebSocket,
    UnitStateDelta,
    UserContext,
)
from aiomelcloudhome.models.telemetry import TelemetryValue
import pytest

from homeassistant.components.melcloud_home.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)

MOCK_USER_INPUT = {
    CONF_EMAIL: "user@example.com",
    CONF_PASSWORD: "thatyouevenlookedheretoseethepassword",
}

MOCK_REAUTH_INPUT = {
    CONF_EMAIL: "new_user@example.com",
    CONF_PASSWORD: "newpassword",
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.melcloud_home.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def websocket_updates() -> asyncio.Queue[UnitStateDelta | Exception]:
    """Queue driving the mocked websocket stream."""
    return asyncio.Queue()


@pytest.fixture
def mock_websocket(
    websocket_updates: asyncio.Queue[UnitStateDelta | Exception],
) -> AsyncMock:
    """Mock the MELCloud Home websocket."""
    websocket = AsyncMock(MELCloudHomeWebSocket)

    async def stream() -> AsyncIterator[UnitStateDelta]:
        while True:
            update = await websocket_updates.get()
            if isinstance(update, Exception):
                raise update
            yield update
            websocket_updates.task_done()

    websocket.stream = stream
    return websocket


@pytest.fixture
def mock_melcloud_client(mock_websocket: AsyncMock) -> Generator[AsyncMock]:
    """Mock MELCloud Home client."""
    client = AsyncMock(MELCloudHome)
    client.websocket.return_value = mock_websocket
    client.get_context.return_value = UserContext.model_validate(
        load_json_object_fixture("context.json", DOMAIN)
    )
    client.get_energy_telemetry.return_value = [
        TelemetryValue.model_validate(value)
        for value in load_json_array_fixture("energy.json", DOMAIN)
    ]

    with (
        patch(
            "homeassistant.components.melcloud_home.MELCloudHome",
            return_value=client,
        ),
        patch(
            "homeassistant.components.melcloud_home.config_flow.MELCloudHome",
            return_value=client,
        ),
    ):
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a MELCloud Home config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="user-uuid-1",
        title=MOCK_USER_INPUT[CONF_EMAIL],
        data=MOCK_USER_INPUT,
        entry_id="config-entry-uuid-1",
    )
