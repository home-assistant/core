"""Mastodon tests configuration."""

from collections.abc import Generator
from unittest.mock import patch

from mashumaro.codecs.orjson import ORJSONDecoder
import pytest

from homeassistant.components.mastodon.const import CONF_BASE_URL, DOMAIN
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_NAME,
)

from tests.common import MockConfigEntry, load_fixture
from tests.components.smhi.common import AsyncMock


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.mastodon.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_mastodon_client() -> Generator[AsyncMock]:
    """Mock a Mastodon client."""
    with (
        patch(
            "homeassistant.components.mastodon.utils.Mastodon",
            autospec=True,
        ) as mock_client,
    ):
        client = mock_client.return_value
        client.instance.return_value = ORJSONDecoder(dict).decode(
            load_fixture("instance.json", DOMAIN)
        )
        client.account_verify_credentials.return_value = ORJSONDecoder(dict).decode(
            load_fixture("account_verify_credentials.json", DOMAIN)
        )
        client.status_post.return_value = None
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Mastodon",
        data={
            CONF_BASE_URL: "https://mastodon.social",
            CONF_CLIENT_ID: "client_id",
            CONF_CLIENT_SECRET: "client_secret",
            CONF_ACCESS_TOKEN: "access_token",
            CONF_NAME: "trwnh",
        },
        entry_id="01J35M4AH9HYRC2V0G6RNVNWJH",
        unique_id="client_id",
    )
