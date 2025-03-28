"""Fixtures for Tedee integration tests."""

from __future__ import annotations

from collections.abc import Generator
import json
from unittest.mock import AsyncMock, MagicMock, patch

from aiotedee.bridge import TedeeBridge
from aiotedee.lock import TedeeLock
import pytest

from homeassistant.components.tedee.const import CONF_LOCAL_ACCESS_TOKEN, DOMAIN
from homeassistant.const import CONF_HOST, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, load_fixture

WEBHOOK_ID = "bq33efxmdi3vxy55q2wbnudbra7iv8mjrq9x0gea33g4zqtd87093pwveg8xcb33"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="My Tedee",
        domain=DOMAIN,
        data={
            CONF_LOCAL_ACCESS_TOKEN: "api_token",
            CONF_HOST: "192.168.1.42",
            CONF_WEBHOOK_ID: WEBHOOK_ID,
        },
        unique_id="0000-0000",
        version=1,
        minor_version=2,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.tedee.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_tedee() -> Generator[MagicMock]:
    """Return a mocked Tedee client."""
    with (
        patch(
            "homeassistant.components.tedee.coordinator.TedeeClient", autospec=True
        ) as tedee_mock,
        patch(
            "homeassistant.components.tedee.config_flow.TedeeClient",
            new=tedee_mock,
        ),
    ):
        tedee = tedee_mock.return_value

        tedee.get_locks.return_value = None
        tedee.sync.return_value = None
        tedee.get_bridges.return_value = [
            TedeeBridge(1234, "0000-0000", "Bridge-AB1C"),
            TedeeBridge(5678, "9999-9999", "Bridge-CD2E"),
        ]
        tedee.get_local_bridge.return_value = TedeeBridge(0, "0000-0000", "Bridge-AB1C")

        tedee.parse_webhook_message.return_value = None
        tedee.register_webhook.return_value = 1
        tedee.delete_webhooks.return_value = None

        locks_json = json.loads(load_fixture("locks.json", DOMAIN))

        lock_list = [TedeeLock(**lock) for lock in locks_json]
        tedee.locks_dict = {lock.lock_id: lock for lock in lock_list}

        yield tedee


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tedee: MagicMock
) -> MockConfigEntry:
    """Set up the Tedee integration for testing."""
    await setup_integration(hass, mock_config_entry)

    return mock_config_entry
