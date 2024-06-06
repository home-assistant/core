"""Test the ista EcoTrend init."""

from unittest.mock import MagicMock

from pyecotrend_ista.exception_classes import (
    InternalServerError,
    KeycloakError,
    LoginError,
    ServerError,
)
import pytest
from requests.exceptions import RequestException
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
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
    [
        ServerError,
        InternalServerError(None),
        RequestException,
        TimeoutError,
    ],
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
    [LoginError(None), KeycloakError],
)
async def test_config_entry_error(
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

    assert ista_config_entry.state is ConfigEntryState.SETUP_ERROR


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
