"""Shared fixtures for Vistapool tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.vistapool.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry, load_json_object_fixture

MOCK_USERNAME = "testuser@example.com"
MOCK_PASSWORD = "testpassword"
MOCK_USER_ID = "firebase-uid-testuser"
MOCK_POOL_ID = "ABCDEF1234567890"
MOCK_POOL_NAME = "My Pool"
MOCK_POOLS = {MOCK_POOL_ID: MOCK_POOL_NAME}


@pytest.fixture
def mock_pool_data() -> dict[str, Any]:
    """Return mock coordinator pool data loaded from the JSON fixture."""
    return load_json_object_fixture("pool_data.json", DOMAIN)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a `MockConfigEntry` for a Vistapool account."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_USERNAME,
        data={
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
        },
        unique_id=MOCK_USER_ID,
    )


@pytest.fixture
def mock_vistapool_auth() -> Generator[MagicMock]:
    """Mock `AquariteAuth` across the config flow and the integration setup."""
    auth = MagicMock()
    auth.authenticate = AsyncMock()
    auth.user_id = MOCK_USER_ID
    auth.is_token_expiring = MagicMock(return_value=False)
    auth.calculate_sleep_duration = MagicMock(return_value=3600)
    with (
        patch("homeassistant.components.vistapool.AquariteAuth", return_value=auth),
        patch(
            "homeassistant.components.vistapool.config_flow.AquariteAuth",
            return_value=auth,
        ),
    ):
        yield auth


@pytest.fixture
def mock_vistapool_client(
    mock_vistapool_auth: MagicMock,
) -> Generator[AsyncMock]:
    """Mock `AquariteClient` across the config flow and the integration setup."""
    client = AsyncMock()
    client.get_pools = AsyncMock(return_value=MOCK_POOLS)
    # The coordinator's manual-refresh fallback awaits `fetch_pool_data`;
    # default to an empty dict so always-on sensors come up with
    # `native_value=None` and module-gated sensors are skipped.
    client.fetch_pool_data = AsyncMock(return_value={})
    # The token-refresh loop awaits `auth.get_client()` and expects
    # `(client, refreshed)`.
    mock_vistapool_auth.get_client = AsyncMock(return_value=(client, False))
    with (
        patch("homeassistant.components.vistapool.AquariteClient", return_value=client),
        patch(
            "homeassistant.components.vistapool.config_flow.AquariteClient",
            return_value=client,
        ),
    ):
        yield client
