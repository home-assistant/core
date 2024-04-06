"""Test initialization of lamarzocco."""

from unittest.mock import MagicMock, patch

from lmcloud.exceptions import AuthFail, RequestNotSuccessful

from homeassistant.components.lamarzocco.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant

from . import async_init_integration, get_bluetooth_service_info

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lamarzocco: MagicMock,
) -> None:
    """Test loading and unloading the integration."""
    await async_init_integration(hass, mock_config_entry)

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

    await async_init_integration(hass, mock_config_entry)

    assert len(mock_lamarzocco.update_local_machine_status.mock_calls) == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_invalid_auth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lamarzocco: MagicMock,
) -> None:
    """Test auth error during setup."""
    mock_lamarzocco.update_local_machine_status.side_effect = AuthFail("")
    await async_init_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert len(mock_lamarzocco.update_local_machine_status.mock_calls) == 1

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == mock_config_entry.entry_id


async def test_bluetooth_is_set_from_discovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lamarzocco: MagicMock,
) -> None:
    """Assert we're not searching for a new BT device when we already found one previously."""

    # remove the bluetooth configuration from entry
    data = mock_config_entry.data.copy()
    del data[CONF_NAME]
    del data[CONF_MAC]
    hass.config_entries.async_update_entry(mock_config_entry, data=data)

    service_info = get_bluetooth_service_info(
        mock_lamarzocco.model_name, mock_lamarzocco.serial_number
    )
    with patch(
        "homeassistant.components.lamarzocco.coordinator.async_discovered_service_info",
        return_value=[service_info],
    ):
        await async_init_integration(hass, mock_config_entry)
    mock_lamarzocco.init_bluetooth_with_known_device.assert_called_once()
    assert mock_config_entry.data[CONF_NAME] == service_info.name
    assert mock_config_entry.data[CONF_MAC] == service_info.address
