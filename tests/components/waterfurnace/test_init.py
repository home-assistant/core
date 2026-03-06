"""Tests for WaterFurnace integration setup."""

from unittest.mock import Mock

from waterfurnace.waterfurnace import WFCredentialError

from homeassistant.components.waterfurnace.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_auth_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_waterfurnace_client: Mock,
) -> None:
    """Test setup fails with auth error."""
    mock_waterfurnace_client.login.side_effect = WFCredentialError(
        "Invalid credentials"
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_multi_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_waterfurnace_client_multi_device: Mock,
) -> None:
    """Test setup with multiple devices creates multiple coordinators."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert isinstance(mock_config_entry.runtime_data, dict)
    assert len(mock_config_entry.runtime_data) == 2
    assert "TEST_GWID_12345" in mock_config_entry.runtime_data
    assert "TEST_GWID_67890" in mock_config_entry.runtime_data


async def test_migrate_unique_id(
    hass: HomeAssistant, mock_waterfurnace_client: Mock
) -> None:
    """Test migration from gwid to username unique_id."""
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        title="WaterFurnace test_user",
        data={
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_password",
        },
        unique_id="TEST_GWID_12345",
        version=1,
        minor_version=1,
    )
    old_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(old_entry.entry_id)
    await hass.async_block_till_done()

    assert old_entry.state is ConfigEntryState.LOADED
    assert old_entry.unique_id == "test_user"
