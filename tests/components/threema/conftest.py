"""Fixtures for Threema Gateway integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.threema.const import (
    CONF_API_SECRET,
    CONF_GATEWAY_ID,
    CONF_PRIVATE_KEY,
    DOMAIN,
    SUBENTRY_TYPE_RECIPIENT,
)
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.const import CONF_RECIPIENT

from tests.common import MockConfigEntry

MOCK_GATEWAY_ID = "*TESTGWY"
MOCK_API_SECRET = "test_secret_key_12345"
MOCK_PRIVATE_KEY = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
MOCK_PUBLIC_KEY = "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"
MOCK_RECIPIENT_ID = "ABCD1234"
MOCK_SUBENTRY_ID = "mock_subentry_id"

RECIPIENT_SUBENTRY: ConfigSubentryDataWithId = {
    "data": {CONF_RECIPIENT: MOCK_RECIPIENT_ID},
    "subentry_id": MOCK_SUBENTRY_ID,
    "subentry_type": SUBENTRY_TYPE_RECIPIENT,
    "title": MOCK_RECIPIENT_ID,
    "unique_id": MOCK_RECIPIENT_ID,
}


@pytest.fixture
def mock_subentries() -> list[ConfigSubentryDataWithId]:
    """Fixture providing one recipient subentry by default; override to []  when not needed."""
    return [RECIPIENT_SUBENTRY]


@pytest.fixture
def mock_config_entry(
    mock_subentries: list[ConfigSubentryDataWithId],
) -> MockConfigEntry:
    """Return a mocked config entry for basic mode (no encryption)."""
    return MockConfigEntry(
        title=f"Threema {MOCK_GATEWAY_ID}",
        domain=DOMAIN,
        data={
            CONF_GATEWAY_ID: MOCK_GATEWAY_ID,
            CONF_API_SECRET: MOCK_API_SECRET,
        },
        unique_id=MOCK_GATEWAY_ID,
        subentries_data=[*mock_subentries],
    )


@pytest.fixture
def mock_config_entry_with_keys(
    mock_subentries: list[ConfigSubentryDataWithId],
) -> MockConfigEntry:
    """Return a mocked config entry for E2E encrypted mode."""
    return MockConfigEntry(
        title=f"Threema {MOCK_GATEWAY_ID}",
        domain=DOMAIN,
        data={
            CONF_GATEWAY_ID: MOCK_GATEWAY_ID,
            CONF_API_SECRET: MOCK_API_SECRET,
            CONF_PRIVATE_KEY: MOCK_PRIVATE_KEY,
        },
        unique_id=MOCK_GATEWAY_ID,
        subentries_data=[*mock_subentries],
    )


@pytest.fixture
def mock_credentials() -> Generator[AsyncMock]:
    """Mock ThreemaAPIClient.validate_credentials to succeed by default."""
    with patch(
        "homeassistant.components.threema.client.ThreemaAPIClient.validate_credentials",
        new_callable=AsyncMock,
    ) as mock:
        yield mock


@pytest.fixture
def mock_send_message() -> Generator[AsyncMock]:
    """Mock ThreemaAPIClient.send_text_message to return a message ID."""
    with patch(
        "homeassistant.components.threema.client.ThreemaAPIClient.send_text_message",
        new_callable=AsyncMock,
        return_value="mock_message_id",
    ) as mock:
        yield mock
