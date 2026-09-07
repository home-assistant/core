"""Tests for the GARDENA smart local integration setup."""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp

from homeassistant.components.gardena_smart_local import (
    _async_exclude_and_report_failure,
)
from homeassistant.components.gardena_smart_local.const import DEFAULT_PORT, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry

MOCK_DATA = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: DEFAULT_PORT,
    CONF_PASSWORD: "testpassword",
}


async def test_setup_rejected_password_is_auth_error(hass: HomeAssistant) -> None:
    """A gateway 401 during setup fails the entry instead of retrying forever."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)

    with patch(
        "aiohttp.ClientSession.ws_connect",
        side_effect=aiohttp.WSServerHandshakeError(
            request_info=MagicMock(), history=(), status=401, message="Unauthorized"
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_gateway_offline_is_retried(hass: HomeAssistant) -> None:
    """A connection failure during setup keeps the entry in retry state."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)

    with patch(
        "aiohttp.ClientSession.ws_connect",
        side_effect=aiohttp.ClientConnectionError("Connection refused"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_exclude_success_creates_no_issue(hass: HomeAssistant) -> None:
    """A confirmed exclusion does not warn the user."""
    coordinator = MagicMock()
    coordinator.async_exclude_device = AsyncMock(return_value=True)

    await _async_exclude_and_report_failure(hass, coordinator, "dev-1")

    coordinator.async_exclude_device.assert_awaited_once_with("dev-1")
    assert ir.async_get(hass).async_get_issue(DOMAIN, "exclude_failed_dev-1") is None


async def test_exclude_retry_success_clears_issue(hass: HomeAssistant) -> None:
    """Removing a still-paired device again resolves the earlier warning."""
    coordinator = MagicMock()
    coordinator.async_exclude_device = AsyncMock(return_value=False)
    await _async_exclude_and_report_failure(hass, coordinator, "dev-1")
    assert ir.async_get(hass).async_get_issue(DOMAIN, "exclude_failed_dev-1")

    coordinator.async_exclude_device = AsyncMock(return_value=True)
    await _async_exclude_and_report_failure(hass, coordinator, "dev-1")

    assert ir.async_get(hass).async_get_issue(DOMAIN, "exclude_failed_dev-1") is None


async def test_exclude_failure_creates_repair_issue(hass: HomeAssistant) -> None:
    """A gateway that does not confirm exclusion is surfaced to the user."""
    coordinator = MagicMock()
    coordinator.async_exclude_device = AsyncMock(return_value=False)

    await _async_exclude_and_report_failure(hass, coordinator, "dev-1")

    issue = ir.async_get(hass).async_get_issue(DOMAIN, "exclude_failed_dev-1")
    assert issue is not None
    assert issue.translation_key == "exclude_failed"
    assert issue.translation_placeholders == {"device_id": "dev-1"}
