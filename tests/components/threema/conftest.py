"""Fixtures for Threema Gateway integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.threema.const import (
    CONF_API_SECRET,
    CONF_GATEWAY_ID,
    CONF_PRIVATE_KEY,
    CONF_PUBLIC_KEY,
    CONF_RECIPIENT,
    DOMAIN,
    SUBENTRY_TYPE_RECIPIENT,
)

from tests.common import MockConfigEntry

MOCK_GATEWAY_ID = "*TESTGWY"
MOCK_API_SECRET = "test_secret_key_12345"
MOCK_PRIVATE_KEY = (
    "private:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)
MOCK_PUBLIC_KEY = (
    "public:fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"
)
MOCK_RECIPIENT_ID = "ABCD1234"
MOCK_SUBENTRY_ID = "mock_subentry_id"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(
        title=f"Threema {MOCK_GATEWAY_ID}",
        domain=DOMAIN,
        data={
            CONF_GATEWAY_ID: MOCK_GATEWAY_ID,
            CONF_API_SECRET: MOCK_API_SECRET,
        },
        unique_id=MOCK_GATEWAY_ID,
    )


@pytest.fixture
def mock_config_entry_with_keys() -> MockConfigEntry:
    """Return a mocked config entry with encryption keys."""
    return MockConfigEntry(
        title=f"Threema {MOCK_GATEWAY_ID}",
        domain=DOMAIN,
        data={
            CONF_GATEWAY_ID: MOCK_GATEWAY_ID,
            CONF_API_SECRET: MOCK_API_SECRET,
            CONF_PRIVATE_KEY: MOCK_PRIVATE_KEY,
            CONF_PUBLIC_KEY: MOCK_PUBLIC_KEY,
        },
        unique_id=MOCK_GATEWAY_ID,
    )


@pytest.fixture
def mock_config_entry_with_subentry() -> MockConfigEntry:
    """Return a mocked config entry with a recipient subentry."""
    return MockConfigEntry(
        title=f"Threema {MOCK_GATEWAY_ID}",
        domain=DOMAIN,
        data={
            CONF_GATEWAY_ID: MOCK_GATEWAY_ID,
            CONF_API_SECRET: MOCK_API_SECRET,
        },
        unique_id=MOCK_GATEWAY_ID,
        subentries_data=[
            {
                "data": {CONF_RECIPIENT: MOCK_RECIPIENT_ID},
                "subentry_id": MOCK_SUBENTRY_ID,
                "subentry_type": SUBENTRY_TYPE_RECIPIENT,
                "title": MOCK_RECIPIENT_ID,
                "unique_id": MOCK_RECIPIENT_ID,
            },
        ],
    )


@pytest.fixture
def mock_connection() -> Generator[MagicMock]:
    """Mock the Threema Gateway Connection."""
    with patch(
        "homeassistant.components.threema.client.Connection", autospec=True
    ) as connection_class:
        connection = MagicMock()
        connection.__aenter__ = AsyncMock(return_value=connection)
        connection.__aexit__ = AsyncMock(return_value=None)
        connection.get_credits = AsyncMock(return_value=100)
        connection_class.return_value = connection
        yield connection


@pytest.fixture
def mock_send() -> Generator[MagicMock]:
    """Mock TextMessage and SimpleTextMessage send methods."""
    with (
        patch(
            "homeassistant.components.threema.client.TextMessage", autospec=True
        ) as e2e_mock,
        patch(
            "homeassistant.components.threema.client.SimpleTextMessage", autospec=True
        ) as simple_mock,
    ):
        e2e_instance = MagicMock()
        e2e_instance.send = AsyncMock(return_value="mock_message_id")
        e2e_mock.return_value = e2e_instance

        simple_instance = MagicMock()
        simple_instance.send = AsyncMock(return_value="mock_message_id")
        simple_mock.return_value = simple_instance

        yield MagicMock(e2e=e2e_mock, simple=simple_mock)
