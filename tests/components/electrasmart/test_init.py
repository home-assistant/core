"""Tests for the Electra Smart integration setup."""

from json import loads
from unittest.mock import AsyncMock, Mock, patch

from electrasmart.api import ElectraApiError, ElectraIntruderLockoutError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_load_fixture
from syrupy.assertion import SnapshotAssertion

from homeassistant import config_entries
from homeassistant.components.electrasmart.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr


@pytest.mark.usefixtures("setup_integration")
async def test_device_registry(
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the device registry entry, including the network MAC connection."""
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "a8032ab12345"), config_entry.entry_id
    )
    assert device_entry == snapshot


async def test_reauth_on_intruder_lockout(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A locked out account asks for reauthentication instead of retrying setup."""
    config_entry.add_to_hass(hass)

    mock_generate_token = loads(
        await async_load_fixture(hass, "generate_token_response.json", DOMAIN)
    )
    mock_api = Mock(
        devices=[],
        fetch_devices=AsyncMock(
            side_effect=ElectraIntruderLockoutError("Failed to retrieve SID")
        ),
    )
    with (
        patch(
            "homeassistant.components.electrasmart.ElectraAPI", return_value=mock_api
        ),
        patch(
            "electrasmart.api.ElectraAPI.generate_new_token",
            return_value=mock_generate_token,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == config_entries.SOURCE_REAUTH


async def test_setup_retries_when_the_api_cannot_be_reached(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """An API error during setup asks Home Assistant to retry."""
    config_entry.add_to_hass(hass)

    mock_api = Mock(
        devices=[],
        fetch_devices=AsyncMock(side_effect=ElectraApiError("Cannot reach the API")),
    )
    with patch(
        "homeassistant.components.electrasmart.ElectraAPI", return_value=mock_api
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_update_listener_reloads_the_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_api: Mock
) -> None:
    """An updated config entry reloads the integration."""
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.electrasmart.ElectraAPI", return_value=mock_api
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED

        assert hass.config_entries.async_update_entry(config_entry, title="Electra")
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert mock_api.fetch_devices.await_count == 2
