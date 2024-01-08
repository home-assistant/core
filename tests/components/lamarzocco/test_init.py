"""Test initialization of lamarzocco."""
from unittest.mock import MagicMock

from lmcloud.exceptions import AuthFail, BluetoothDeviceNotFound, RequestNotSuccessful

from homeassistant.components.lamarzocco.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lamarzocco: MagicMock,
) -> None:
    """Test loading and unloading the integration."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lamarzocco: MagicMock,
) -> None:
    """Test the La Marzocco configuration entry not ready."""
    mock_lamarzocco.update_local_machine_status.side_effect = RequestNotSuccessful("")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(mock_lamarzocco.update_local_machine_status.mock_calls) == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_invalid_auth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lamarzocco: MagicMock,
) -> None:
    """Test auth error during setup."""
    mock_lamarzocco.update_local_machine_status.side_effect = AuthFail("")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert len(mock_lamarzocco.update_local_machine_status.mock_calls) == 1

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "user"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == mock_config_entry.entry_id


async def test_first_refresh_request_fail(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lamarzocco: MagicMock,
) -> None:
    """Test if the first refresh throws an error."""
    mock_lamarzocco.init_cloud_api.side_effect = RequestNotSuccessful("")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_first_refresh_auth_fail(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lamarzocco: MagicMock,
) -> None:
    """Test if the first refresh throws an Authfail."""
    mock_lamarzocco.init_cloud_api.side_effect = AuthFail("")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    flow = flows[0]
    assert flow.get("step_id") == "user"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == mock_config_entry.entry_id


async def test_first_refresh_bluetooth_fail(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lamarzocco: MagicMock,
) -> None:
    """Test if the first refresh throws BluetoothDeviceNotFound."""
    mock_lamarzocco.init_bluetooth.side_effect = BluetoothDeviceNotFound("")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    assert coordinator._use_bluetooth is False
