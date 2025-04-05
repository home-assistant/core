"""Conftest for the SyncThru integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.syncthru import DOMAIN

from tests.common import load_json_object_fixture


@pytest.fixture
def mock_syncthru() -> Generator[AsyncMock]:
    """Mock the SyncThru class."""
    with (
        patch(
            "homeassistant.components.syncthru.SyncThru",
            autospec=True,
        ) as mock_syncthru,
        patch(
            "homeassistant.components.syncthru.config_flow.SyncThru", new=mock_syncthru
        ),
    ):
        client = mock_syncthru.return_value
        client.model.return_value = "C430W"
        client.is_unknown_state.return_value = False
        client.raw.return_value = load_json_object_fixture("state.json", DOMAIN)
        yield client
