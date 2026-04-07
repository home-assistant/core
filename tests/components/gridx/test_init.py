"""Tests for the GridX integration setup."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from homeassistant.components.gridx.const import CONF_OEM, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .conftest import OEM, PASSWORD, USERNAME

from tests.common import MockConfigEntry


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a mock GridX config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_OEM: OEM},
        title=USERNAME,
        unique_id=USERNAME.lower(),
    )
    entry.add_to_hass(hass)
    return entry


@pytest.mark.parametrize(
    "ignore_missing_translations",
    [
        [
            "component.homeassistant.issues.config_entry_reauth.title",
            "component.homeassistant.issues.config_entry_reauth.description",
        ]
    ],
)
async def test_setup_permission_error(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """PermissionError during connector creation raises ConfigEntryAuthFailed."""
    with patch(
        "homeassistant.components.gridx.async_create_connector",
        AsyncMock(side_effect=PermissionError("unauthorized")),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    "ignore_missing_translations",
    [
        [
            "component.homeassistant.issues.config_entry_reauth.title",
            "component.homeassistant.issues.config_entry_reauth.description",
        ]
    ],
)
async def test_setup_http_status_401(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """HTTPStatusError with 401 raises ConfigEntryAuthFailed."""
    response = MagicMock()
    response.status_code = 401
    err = httpx.HTTPStatusError(
        "401 Unauthorized", request=MagicMock(), response=response
    )
    with patch(
        "homeassistant.components.gridx.async_create_connector",
        AsyncMock(side_effect=err),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_http_status_500(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """HTTPStatusError with 500 raises ConfigEntryNotReady."""
    response = MagicMock()
    response.status_code = 500
    err = httpx.HTTPStatusError(
        "500 Internal Server Error", request=MagicMock(), response=response
    )
    with patch(
        "homeassistant.components.gridx.async_create_connector",
        AsyncMock(side_effect=err),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_http_error(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """httpx.HTTPError raises ConfigEntryNotReady."""
    with patch(
        "homeassistant.components.gridx.async_create_connector",
        AsyncMock(side_effect=httpx.HTTPError("connection failed")),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_runtime_error(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """RuntimeError during connector creation raises ConfigEntryNotReady."""
    with patch(
        "homeassistant.components.gridx.async_create_connector",
        AsyncMock(side_effect=RuntimeError("unexpected")),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
