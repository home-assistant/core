"""Test helpers for Husqvarna Automower."""

import asyncio
from collections.abc import Generator
import time
from unittest.mock import AsyncMock, patch

from aioautomower.model import MowerAttributes
from aioautomower.session import AutomowerSession, _MowerCommands
from aioautomower.utils import mower_list_to_dictionary_dataclass
from aiohttp import ClientWebSocketResponse
import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.husqvarna_automower.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .const import CLIENT_ID, CLIENT_SECRET, USER_ID

from tests.common import MockConfigEntry, load_fixture, load_json_value_fixture


@pytest.fixture(name="jwt")
def load_jwt_fixture() -> str:
    """Load Fixture data."""
    return load_fixture("jwt", DOMAIN)


@pytest.fixture(name="expires_at")
def mock_expires_at() -> float:
    """Fixture to set the oauth token expiration time."""
    return time.time() + 3600


@pytest.fixture(name="scope")
def mock_scope() -> str:
    """Fixture to set correct scope for the token."""
    return "iam:read amc:api"


@pytest.fixture(name="mower_time_zone")
async def mock_time_zone(hass: HomeAssistant) -> dict[str, MowerAttributes]:
    """Fixture to set correct scope for the token."""
    return await dt_util.async_get_time_zone("Europe/Berlin")


@pytest.fixture(name="values")
def mock_values(mower_time_zone) -> dict[str, MowerAttributes]:
    """Fixture to set correct scope for the token."""
    return mower_list_to_dictionary_dataclass(
        load_json_value_fixture("mower.json", DOMAIN),
        mower_time_zone,
    )


@pytest.fixture
def mock_config_entry(jwt: str, expires_at: int, scope: str) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Husqvarna Automower of Erika Mustermann",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": jwt,
                "scope": scope,
                "expires_in": 86399,
                "refresh_token": "3012bc9f-7a65-4240-b817-9154ffdcc30f",
                "provider": "husqvarna",
                "user_id": USER_ID,
                "token_type": "Bearer",
                "expires_at": expires_at,
            },
        },
        unique_id=USER_ID,
        entry_id="automower_test",
    )


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(
            CLIENT_ID,
            CLIENT_SECRET,
        ),
        DOMAIN,
    )


@pytest.fixture
def mock_automower_client(values) -> Generator[AsyncMock]:
    """Mock a Husqvarna Automower client."""

    async def listen() -> None:
        """Mock listen."""
        listen_block = asyncio.Event()
        await listen_block.wait()
        pytest.fail("Listen was not cancelled!")

    mock = AsyncMock(spec=AutomowerSession)
    mock.auth = AsyncMock(side_effect=ClientWebSocketResponse)
    mock.commands = AsyncMock(spec_set=_MowerCommands)
    mock.get_status.return_value = values
    mock.start_listening = AsyncMock(side_effect=listen)

    with patch(
        "homeassistant.components.husqvarna_automower.AutomowerSession",
        return_value=mock,
    ):
        yield mock
