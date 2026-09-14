"""Test init."""

from unittest.mock import AsyncMock, patch

from aioflo.errors import RequestError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.flo.const import CONF_USE_SSO
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_setup_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test migration of config entry from v1."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    assert (
        dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
        == snapshot
    )

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_persists_sso_flag(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test setup stores use_sso when legacy auth fails and SSO succeeds."""
    config_entry.add_to_hass(hass)
    assert CONF_USE_SSO not in config_entry.data

    client = AsyncMock()
    client.user.get_info = AsyncMock(return_value={"locations": []})

    with patch(
        "homeassistant.components.flo.async_get_api",
        new_callable=AsyncMock,
        side_effect=[RequestError("legacy failed"), client],
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.data[CONF_USE_SSO] is True
