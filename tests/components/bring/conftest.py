"""Common fixtures for the Bring! tests."""

from collections.abc import Generator
import json
from typing import cast
from unittest.mock import AsyncMock, patch
import uuid

from bring_api.types import BringAuthResponse
import pytest

from homeassistant.components.bring import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from tests.common import MockConfigEntry, load_fixture

EMAIL = "test-email"
PASSWORD = "test-password"

UUID = "00000000-00000000-00000000-00000000"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.bring.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_bring_client() -> Generator[AsyncMock]:
    """Mock a Bring client."""
    with (
        patch(
            "homeassistant.components.bring.Bring",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.bring.config_flow.Bring",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.uuid = UUID
        client.login.return_value = cast(BringAuthResponse, {"name": "Bring"})
        client.load_lists.return_value = json.loads(load_fixture("lists.json", DOMAIN))
        client.get_list.return_value = json.loads(load_fixture("items.json", DOMAIN))
        yield client


@pytest.fixture
def mock_uuid() -> Generator[AsyncMock]:
    """Mock uuid."""

    with patch(
        "homeassistant.components.bring.todo.uuid.uuid4",
        autospec=True,
    ) as mock_client:
        mock_client.return_value = uuid.UUID("b669ad23-606a-4652-b302-995d34b1cb1c")
        yield mock_client


@pytest.fixture(name="bring_config_entry")
def mock_bring_config_entry() -> MockConfigEntry:
    """Mock bring configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN, data={CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}, unique_id=UUID
    )
