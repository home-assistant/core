"""Common fixtures for the ntfy tests."""

from collections.abc import Generator
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from aiontfy import Account, AccountTokenResponse
import pytest

from homeassistant.components.ntfy.const import CONF_TOPIC, DOMAIN
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_TOKEN, CONF_URL, CONF_USERNAME

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ntfy.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_aiontfy() -> Generator[AsyncMock]:
    """Mock aiontfy."""

    with (
        patch("homeassistant.components.ntfy.Ntfy", autospec=True) as mock_client,
        patch("homeassistant.components.ntfy.config_flow.Ntfy", new=mock_client),
    ):
        client = mock_client.return_value

        client.publish.return_value = {}
        client.account.return_value = Account.from_json(
            load_fixture("account.json", DOMAIN)
        )
        client.generate_token.return_value = AccountTokenResponse(
            token="token", last_access=datetime.now()
        )
        yield client


@pytest.fixture(autouse=True)
def mock_random() -> Generator[MagicMock]:
    """Mock random."""

    with patch(
        "homeassistant.components.ntfy.config_flow.random.choices",
        return_value=["randomtopic"],
    ) as mock_client:
        yield mock_client


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Mock ntfy configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="ntfy.sh",
        data={
            CONF_URL: "https://ntfy.sh/",
            CONF_USERNAME: None,
            CONF_TOKEN: "token",
        },
        entry_id="123456789",
        subentries_data=[
            ConfigSubentryData(
                data={CONF_TOPIC: "mytopic"},
                subentry_id="ABCDEF",
                subentry_type="topic",
                title="mytopic",
                unique_id="mytopic",
            )
        ],
    )
