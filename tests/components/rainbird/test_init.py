"""Tests for rainbird initialization."""

from __future__ import annotations

from http import HTTPStatus

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant

from .conftest import (
    CONFIG_ENTRY_DATA,
    CONFIG_ENTRY_DATA_OLD_FORMAT,
    MAC_ADDRESS,
    MAC_ADDRESS_UNIQUE_ID,
    MODEL_AND_VERSION_RESPONSE,
    WIFI_PARAMS_RESPONSE,
    mock_json_response,
    mock_response,
    mock_response_error,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMockResponse


@pytest.mark.parametrize(
    ("config_entry_data", "initial_response"),
    [
        (CONFIG_ENTRY_DATA, None),
    ],
    ids=["config_entry"],
)
async def test_init_success(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    responses: list[AiohttpClientMockResponse],
    initial_response: AiohttpClientMockResponse | None,
) -> None:
    """Test successful setup and unload."""
    if initial_response:
        responses.insert(0, initial_response)

    await config_entry.async_setup(hass)
    assert config_entry.state == ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("config_entry_data", "responses", "config_entry_state"),
    [
        (
            CONFIG_ENTRY_DATA,
            [mock_response_error(HTTPStatus.SERVICE_UNAVAILABLE)],
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            CONFIG_ENTRY_DATA,
            [mock_response_error(HTTPStatus.INTERNAL_SERVER_ERROR)],
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            CONFIG_ENTRY_DATA,
            [
                mock_response(MODEL_AND_VERSION_RESPONSE),
                mock_response_error(HTTPStatus.SERVICE_UNAVAILABLE),
            ],
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            CONFIG_ENTRY_DATA,
            [
                mock_response(MODEL_AND_VERSION_RESPONSE),
                mock_response_error(HTTPStatus.INTERNAL_SERVER_ERROR),
            ],
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
    ids=[
        "unavailable",
        "server-error",
        "coordinator-unavailable",
        "coordinator-server-error",
    ],
)
async def test_communication_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    config_entry_state: list[ConfigEntryState],
) -> None:
    """Test unable to talk to device on startup, which fails setup."""
    await config_entry.async_setup(hass)
    assert config_entry.state == config_entry_state


@pytest.mark.parametrize(
    ("config_entry_unique_id", "config_entry_data"),
    [
        (
            None,
            {**CONFIG_ENTRY_DATA, "mac": None},
        ),
    ],
    ids=["config_entry"],
)
async def test_fix_unique_id(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    responses: list[AiohttpClientMockResponse],
) -> None:
    """Test fix of a config entry with no unique id."""

    responses.insert(0, mock_json_response(WIFI_PARAMS_RESPONSE))

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state == ConfigEntryState.NOT_LOADED
    assert entries[0].unique_id is None
    assert entries[0].data.get(CONF_MAC) is None

    assert await setup_integration()

    # Verify config entry now has a unique id
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state == ConfigEntryState.LOADED
    assert entries[0].unique_id == MAC_ADDRESS_UNIQUE_ID
    assert entries[0].data.get(CONF_MAC) == MAC_ADDRESS


@pytest.mark.parametrize(
    (
        "config_entry_unique_id",
        "config_entry_data",
        "initial_response",
        "expected_warning",
    ),
    [
        (
            None,
            CONFIG_ENTRY_DATA_OLD_FORMAT,
            mock_response_error(HTTPStatus.SERVICE_UNAVAILABLE),
            "Unable to fix missing unique id:",
        ),
        (
            None,
            CONFIG_ENTRY_DATA_OLD_FORMAT,
            mock_response_error(HTTPStatus.NOT_FOUND),
            "Unable to fix missing unique id:",
        ),
        (
            None,
            CONFIG_ENTRY_DATA_OLD_FORMAT,
            mock_response("bogus"),
            "Unable to fix missing unique id (mac address was None)",
        ),
    ],
    ids=["service_unavailable", "not_found", "unexpected_response_format"],
)
async def test_fix_unique_id_failure(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    initial_response: AiohttpClientMockResponse,
    responses: list[AiohttpClientMockResponse],
    expected_warning: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failure during fix of a config entry with no unique id."""

    responses.insert(0, initial_response)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state == ConfigEntryState.NOT_LOADED
    assert entries[0].unique_id is None

    assert await setup_integration()

    # Config entry is loaded, but not updated
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state == ConfigEntryState.LOADED
    assert entries[0].unique_id is None

    assert expected_warning in caplog.text


@pytest.mark.parametrize(
    ("config_entry_unique_id"),
    [(MAC_ADDRESS_UNIQUE_ID)],
)
async def test_fix_unique_id_duplicate(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    responses: list[AiohttpClientMockResponse],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a config entry unique id already exists during fix."""

    # Add a second config entry that has no unique id, but has the same
    # mac address. When fixing the unique id, it can't use the mac address
    # since it already exists.
    other_entry = MockConfigEntry(
        unique_id=None,
        domain=DOMAIN,
        data=CONFIG_ENTRY_DATA_OLD_FORMAT,
    )
    other_entry.add_to_hass(hass)

    # Responses for the second config entry. This first fetches wifi params
    # to repair the unique id.
    responses_copy = [*responses]
    responses.append(mock_json_response(WIFI_PARAMS_RESPONSE))
    responses.extend(responses_copy)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 2
    assert entries[0].state == ConfigEntryState.NOT_LOADED
    assert entries[0].unique_id is MAC_ADDRESS_UNIQUE_ID
    assert entries[1].state == ConfigEntryState.NOT_LOADED
    assert entries[1].unique_id is None

    assert await setup_integration()

    # Config entry unique id could not be updated since it already exists
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 2
    assert entries[0].state == ConfigEntryState.LOADED
    assert entries[0].unique_id is MAC_ADDRESS_UNIQUE_ID
    assert entries[1].state == ConfigEntryState.LOADED
    assert entries[1].unique_id is None

    assert "Unable to fix missing unique id (already exists)" in caplog.text
