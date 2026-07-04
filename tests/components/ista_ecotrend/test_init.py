"""Test the ista EcoTrend init."""

from unittest.mock import MagicMock, patch

from pyecotrend_ista import KeycloakError, LoginError, ParserError, ServerError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ista_ecotrend.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_ista")
async def test_entry_setup_unload(
    hass: HomeAssistant, ista_config_entry: MockConfigEntry
) -> None:
    """Test integration setup and unload."""

    ista_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(ista_config_entry.entry_id)
    await hass.async_block_till_done()

    assert ista_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(ista_config_entry.entry_id)
    await hass.async_block_till_done()

    assert ista_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect"),
    [ServerError, ParserError],
)
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    ista_config_entry: MockConfigEntry,
    mock_ista: MagicMock,
    side_effect: Exception,
) -> None:
    """Test config entry not ready."""
    mock_ista.login.side_effect = side_effect
    ista_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(ista_config_entry.entry_id)
    await hass.async_block_till_done()

    assert ista_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("side_effect"),
    [LoginError, KeycloakError],
)
async def test_config_entry_auth_failed(
    hass: HomeAssistant,
    ista_config_entry: MockConfigEntry,
    mock_ista: MagicMock,
    side_effect: Exception,
) -> None:
    """Test config entry auth failed."""
    mock_ista.login.side_effect = side_effect
    ista_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(ista_config_entry.entry_id)
    await hass.async_block_till_done()

    assert ista_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert any(ista_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


@pytest.mark.usefixtures("mock_ista")
async def test_device_registry(
    hass: HomeAssistant,
    ista_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device registry."""
    ista_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(ista_config_entry.entry_id)
    await hass.async_block_till_done()

    assert ista_config_entry.state is ConfigEntryState.LOADED

    for device in dr.async_entries_for_config_entry(
        device_registry, ista_config_entry.entry_id
    ):
        assert device == snapshot


async def test_update_failed(
    hass: HomeAssistant,
    ista_config_entry: MockConfigEntry,
    mock_ista: MagicMock,
) -> None:
    """Test coordinator update failed."""

    with patch(
        "homeassistant.components.ista_ecotrend.PLATFORMS",
        [],
    ):
        mock_ista.get_consumption_data.side_effect = ServerError
        ista_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(ista_config_entry.entry_id)
        await hass.async_block_till_done()

        assert ista_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_auth_failed(
    hass: HomeAssistant, ista_config_entry: MockConfigEntry, mock_ista: MagicMock
) -> None:
    """Test coordinator auth failed and reauth flow started."""
    with patch(
        "homeassistant.components.ista_ecotrend.PLATFORMS",
        [],
    ):
        mock_ista.get_consumption_data.side_effect = LoginError
        ista_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(ista_config_entry.entry_id)
        await hass.async_block_till_done()

        assert ista_config_entry.state is ConfigEntryState.SETUP_ERROR

        flows = hass.config_entries.flow.async_progress()
        assert len(flows) == 1

        flow = flows[0]
        assert flow.get("step_id") == "reauth_confirm"
        assert flow.get("handler") == DOMAIN

        assert "context" in flow
        assert flow["context"].get("source") == SOURCE_REAUTH
        assert flow["context"].get("entry_id") == ista_config_entry.entry_id
