"""Test cases for the refoss_rpc component."""

from unittest.mock import AsyncMock, Mock

from aiorefoss.exceptions import InvalidAuthError, MacAddressMismatchError
import pytest

from homeassistant.components.refoss_rpc.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import set_integration

from tests.common import MockConfigEntry


async def test_entry_unload(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
) -> None:
    """Test entry unload."""
    entity_id = "switch.test_switch"
    entry = await set_integration(hass)

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(entity_id).state is STATE_ON

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get(entity_id).state is STATE_UNAVAILABLE


async def test_setup_entry_not_refoss(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test not refoss_rpc entry."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id) is False
    await hass.async_block_till_done()

    assert "Invalid Host, please try again" in caplog.text


async def test_mac_mismatch_error(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test device MAC address mismatch error."""
    monkeypatch.setattr(
        mock_rpc_device, "initialize", AsyncMock(side_effect=MacAddressMismatchError)
    )

    entry = await set_integration(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_device_auth_error(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test device authentication error."""
    monkeypatch.setattr(
        mock_rpc_device, "initialize", AsyncMock(side_effect=InvalidAuthError)
    )

    entry = await set_integration(hass)
    assert entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id
