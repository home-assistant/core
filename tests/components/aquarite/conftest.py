"""Shared fixtures for Aquarite tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.aquarite.const import DOMAIN

from tests.common import load_json_object_fixture

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
def mock_aquarite_auth() -> Generator[MagicMock]:
    """Mock `AquariteAuth` across the config flow and the integration setup."""
    auth = MagicMock()
    auth.authenticate = AsyncMock()
    auth.user_id = MOCK_USER_ID
    auth.is_token_expiring = MagicMock(return_value=False)
    auth.calculate_sleep_duration = MagicMock(return_value=3600)
    with (
        patch(
            "homeassistant.components.aquarite.AquariteAuth", return_value=auth
        ),
        patch(
            "homeassistant.components.aquarite.config_flow.AquariteAuth",
            return_value=auth,
        ),
    ):
        yield auth


@pytest.fixture
def mock_aquarite_client(
    mock_aquarite_auth: MagicMock,
) -> Generator[AsyncMock]:
    """Mock `AquariteClient` across the config flow and the integration setup."""
    client = AsyncMock()
    client.get_pools = AsyncMock(return_value=MOCK_POOLS)
    # The token-refresh loop awaits `auth.get_client()` and expects
    # `(client, refreshed)`.
    mock_aquarite_auth.get_client = AsyncMock(return_value=(client, False))
    with (
        patch(
            "homeassistant.components.aquarite.AquariteClient", return_value=client
        ),
        patch(
            "homeassistant.components.aquarite.config_flow.AquariteClient",
            return_value=client,
        ),
    ):
        yield client
