"""Tests for Google Drive."""

from collections.abc import Awaitable, Callable, Generator
import time
from unittest.mock import patch

import pytest

from homeassistant.components.google_drive import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

TEST_SHEET_ID = "google-sheet-it"

ComponentSetup = Callable[[], Awaitable[None]]


@pytest.fixture
async def scopes() -> list[str]:
    """Fixture to set the scopes present in the OAuth token."""
    return ["https://www.googleapis.com/auth/drive.file"]


@pytest.fixture
async def config_entry(scopes: list[str]) -> MockConfigEntry:
    """Fixture for MockConfigEntry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_SHEET_ID,
        data={
            "token": {
                "access_token": "mock-access-token",
                "expires_at": time.time() + 3600,
                "scope": " ".join(scopes),
            },
        },
    )


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> Generator[ComponentSetup, None, None]:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    async def func() -> None:
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    with patch(
        "homeassistant.components.google_drive.async_get_config_entry_implementation"
    ):
        yield func

    # Verify clean unload
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert entries[0].state is ConfigEntryState.NOT_LOADED


async def test_setup_success(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test successful setup and unload."""
    await setup_integration()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "scopes",
    [
        [],
        [
            "https://www.googleapis.com/auth/drive.file+plus+extra"
        ],  # Required scope is a prefix
        ["https://www.googleapis.com/auth/drive.readonly"],
    ],
    ids=["no_scope", "required_scope_prefix", "other_scope"],
)
async def test_missing_required_scopes_requires_reauth(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test successful setup and unload."""
    await setup_integration()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"
