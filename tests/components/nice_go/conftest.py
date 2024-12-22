"""Common fixtures for the Nice G.O. tests."""

from collections.abc import Generator
from datetime import datetime
from unittest.mock import AsyncMock, patch

from nice_go import Barrier, BarrierState, ConnectionState
import pytest

from homeassistant.components.nice_go.const import (
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_TOKEN_CREATION_TIME,
    DOMAIN,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from tests.common import MockConfigEntry, load_json_array_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.nice_go.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_nice_go() -> Generator[AsyncMock]:
    """Mock a Nice G.O. client."""
    with (
        patch(
            "homeassistant.components.nice_go.coordinator.NiceGOApi",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.nice_go.config_flow.NiceGOApi",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.authenticate.return_value = "test-refresh-token"
        client.authenticate_refresh.return_value = None
        client.id_token = None
        client.get_all_barriers.return_value = [
            Barrier(
                id=barrier["id"],
                type=barrier["type"],
                controlLevel=barrier["controlLevel"],
                attr=barrier["attr"],
                state=BarrierState(
                    **barrier["state"],
                    connectionState=ConnectionState(**barrier["connectionState"])
                    if barrier.get("connectionState")
                    else None,
                ),
                api=client,
            )
            for barrier in load_json_array_fixture("get_all_barriers.json", DOMAIN)
        ]
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="acefdd4b3a4a0911067d1cf51414201e",
        title="test-email",
        data={
            CONF_EMAIL: "test-email",
            CONF_PASSWORD: "test-password",
            CONF_REFRESH_TOKEN: "test-refresh-token",
            CONF_REFRESH_TOKEN_CREATION_TIME: datetime.now().timestamp(),
        },
        version=1,
        unique_id="test-email",
    )
