"""Fixtures for UniFi Access integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from unifi_access_api import (
    Door,
    DoorLockRelayStatus,
    DoorPositionStatus,
    EmergencyStatus,
)

from homeassistant.components.unifi_access.const import DOMAIN
from homeassistant.const import CONF_API_TOKEN, CONF_HOST, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry

MOCK_HOST = "192.168.1.1"
MOCK_API_TOKEN = "test-api-token-12345"


MOCK_ENTRY_ID = "mock-unifi-access-entry-id"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id=MOCK_ENTRY_ID,
        title="UniFi Access",
        data={
            CONF_HOST: MOCK_HOST,
            CONF_API_TOKEN: MOCK_API_TOKEN,
            CONF_VERIFY_SSL: False,
        },
        version=1,
        minor_version=1,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.unifi_access.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


def _make_door(
    door_id: str = "door-001",
    name: str = "Front Door",
    lock_status: DoorLockRelayStatus = DoorLockRelayStatus.LOCK,
    position_status: DoorPositionStatus = DoorPositionStatus.CLOSE,
    door_thumbnail: str | None = None,
    door_thumbnail_last_update: int | None = None,
) -> Door:
    """Create a mock Door object."""
    return Door(
        id=door_id,
        name=name,
        door_lock_relay_status=lock_status,
        door_position_status=position_status,
        door_thumbnail=door_thumbnail,
        door_thumbnail_last_update=door_thumbnail_last_update,
    )


MOCK_DOORS = [
    _make_door(
        "door-001",
        "Front Door",
        door_thumbnail="/preview/front_door.png",
        door_thumbnail_last_update=1700000000,
    ),
    _make_door(
        "door-002",
        "Back Door",
        lock_status=DoorLockRelayStatus.UNLOCK,
        position_status=DoorPositionStatus.OPEN,
    ),
]


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Return a mocked UniFi Access API client."""
    with (
        patch(
            "homeassistant.components.unifi_access.UnifiAccessApiClient",
            autospec=True,
        ) as client_mock,
        patch(
            "homeassistant.components.unifi_access.config_flow.UnifiAccessApiClient",
            new=client_mock,
        ),
    ):
        client = client_mock.return_value
        client.authenticate = AsyncMock()
        client.get_doors = AsyncMock(return_value=MOCK_DOORS)
        client.get_emergency_status = AsyncMock(
            return_value=EmergencyStatus(evacuation=False, lockdown=False)
        )
        client.set_emergency_status = AsyncMock()
        client.unlock_door = AsyncMock()
        client.get_thumbnail = AsyncMock(return_value=b"")
        client.close = AsyncMock()
        client.start_websocket = MagicMock()
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> MockConfigEntry:
    """Set up the UniFi Access integration for testing."""
    await setup_integration(hass, mock_config_entry)
    return mock_config_entry
