"""Tests for Google Sheets."""
import http
import time
from unittest.mock import patch

import pytest

from homeassistant.components.google_sheets import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceNotFound

from .conftest import TEST_SHEET_ID, ComponentSetup

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup_success(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test successful setup and unload."""
    await setup_integration()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert entries[0].state is ConfigEntryState.NOT_LOADED
    assert not hass.services.async_services().get(DOMAIN, {})


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
    """Test that reauth is invoked when required scopes are not present."""
    await setup_integration()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


@pytest.mark.parametrize("expires_at", [time.time() - 3600], ids=["expired"])
async def test_expired_token_refresh_success(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test expired token is refreshed."""

    aioclient_mock.post(
        "https://oauth2.googleapis.com/token",
        json={
            "access_token": "updated-access-token",
            "refresh_token": "updated-refresh-token",
            "expires_at": time.time() + 3600,
            "expires_in": 3600,
        },
    )

    await setup_integration()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED
    assert entries[0].data["token"]["access_token"] == "updated-access-token"
    assert entries[0].data["token"]["expires_in"] == 3600


@pytest.mark.parametrize(
    ("expires_at", "status", "expected_state"),
    [
        (
            time.time() - 3600,
            http.HTTPStatus.UNAUTHORIZED,
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            time.time() - 3600,
            http.HTTPStatus.INTERNAL_SERVER_ERROR,
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
    ids=["failure_requires_reauth", "transient_failure"],
)
async def test_expired_token_refresh_failure(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
    status: http.HTTPStatus,
    expected_state: ConfigEntryState,
) -> None:
    """Test failure while refreshing token with a transient error."""

    aioclient_mock.post(
        "https://oauth2.googleapis.com/token",
        status=status,
    )

    await setup_integration()

    # Verify a transient failure has occurred
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries[0].state is expected_state


async def test_reload_triggers_reauth(
    hass: HomeAssistant,
    scopes: list[str],
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
) -> None:
    """Test reload can trigger reauth after change in options."""
    await setup_integration()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"sheets_access": "read_write"},
    )
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


async def test_append_sheet(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
) -> None:
    """Test service call appending to a sheet."""
    await setup_integration()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.LOADED

    with patch("homeassistant.components.google_sheets.Client") as mock_client:
        await hass.services.async_call(
            DOMAIN,
            "append_sheet",
            {
                "config_entry": config_entry.entry_id,
                "worksheet": "Sheet1",
                "data": {"foo": "bar"},
            },
            blocking=True,
        )
    assert len(mock_client.mock_calls) == 8


async def test_append_sheet_invalid_config_entry(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    expires_at: int,
    scopes: list[str],
) -> None:
    """Test service call with invalid config entries."""
    config_entry2 = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_SHEET_ID + "2",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": expires_at,
                "scope": " ".join(scopes),
            },
        },
        options={"sheets_access": "read_only"},
    )
    config_entry2.add_to_hass(hass)

    await setup_integration()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry2.state is ConfigEntryState.LOADED

    # Exercise service call on a config entry that does not exist
    with pytest.raises(ValueError, match="Invalid config entry"):
        await hass.services.async_call(
            DOMAIN,
            "append_sheet",
            {
                "config_entry": config_entry.entry_id + "XXX",
                "worksheet": "Sheet1",
                "data": {"foo": "bar"},
            },
            blocking=True,
        )

    # Unload the config entry invoke the service on the unloaded entry id
    await hass.config_entries.async_unload(config_entry2.entry_id)
    await hass.async_block_till_done()
    assert config_entry2.state is ConfigEntryState.NOT_LOADED

    with pytest.raises(ValueError, match="Config entry not loaded"):
        await hass.services.async_call(
            DOMAIN,
            "append_sheet",
            {
                "config_entry": config_entry2.entry_id,
                "worksheet": "Sheet1",
                "data": {"foo": "bar"},
            },
            blocking=True,
        )

    # Unloading the other config entry will de-register the service
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED

    with pytest.raises(ServiceNotFound):
        await hass.services.async_call(
            DOMAIN,
            "append_sheet",
            {
                "config_entry": config_entry.entry_id,
                "worksheet": "Sheet1",
                "data": {"foo": "bar"},
            },
            blocking=True,
        )


async def test_edit_sheet(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
) -> None:
    """Test service call editing a sheet."""
    await setup_integration()

    assert config_entry.state is ConfigEntryState.LOADED

    with patch("homeassistant.components.google_sheets.Client") as mock_client:
        await hass.services.async_call(
            DOMAIN,
            "edit_sheet",
            {
                "config_entry": config_entry.entry_id,
                "worksheet": "Sheet1",
                "data": {"A1": "bar"},
            },
            blocking=True,
        )
    assert len(mock_client.mock_calls) == 4
