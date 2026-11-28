"""Fixtures for the Google Docs integration."""

from collections.abc import Generator
from contextlib import ExitStack
import time
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.google_docs.const import DEFAULT_ACCESS, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import DOCUMENT_ID


@pytest.fixture
def mock_api() -> Generator[dict[str, MagicMock]]:
    """Mock remote operations without bypassing the HA integration."""
    with ExitStack() as stack:
        mocks = {
            name: stack.enter_context(patch(f"gdocs_client.{name}"))
            for name in ("create_document", "get_document", "append_text")
        }
        mocks["create_document"].return_value = {
            "documentId": DOCUMENT_ID,
            "title": "Home Assistant",
        }
        mocks["get_document"].return_value = {
            "documentId": DOCUMENT_ID,
            "title": "Home Assistant",
            "text": "Hello",
        }
        yield mocks


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Return an authorized configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Google Docs",
        unique_id=DOCUMENT_ID,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": time.time() + 3600,
                "scope": DEFAULT_ACCESS,
            },
        },
    )


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Register an OAuth application using public HA credential APIs."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential("client-id", "client-secret"),
        DOMAIN,
    )


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api: dict[str, MagicMock],
    setup_credentials: None,
) -> MockConfigEntry:
    """Load a real Google Docs config entry with only Google calls mocked."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry
