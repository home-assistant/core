"""Test connection options and cleanup."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.bluetooth import inject_bluetooth_service_info

from homeassistant.components.gardena_bluetooth import DISCONNECT_DELAY, get_connection
from homeassistant.components.gardena_bluetooth.const import CONF_PERSISTENT_CONNECTION
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import WATER_TIMER_SERVICE_INFO


@pytest.mark.parametrize("persistent", [False, True])
async def test_connection_delay(hass: HomeAssistant, persistent: bool) -> None:
    """The option selects the delay without opening a connection."""
    with patch(
        "homeassistant.components.gardena_bluetooth.CachedConnection"
    ) as connection:
        get_connection(hass, WATER_TIMER_SERVICE_INFO.address, persistent)
    assert connection.call_args.args[0] == (None if persistent else DISCONNECT_DELAY)


@pytest.mark.parametrize("persistent", [False, True])
async def test_options_reload(
    hass: HomeAssistant, mock_entry: MockConfigEntry, persistent: bool
) -> None:
    """Saving the option persists it and reloads a loaded entry."""
    mock_entry.add_to_hass(hass)
    inject_bluetooth_service_info(hass, WATER_TIMER_SERVICE_INFO)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(mock_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["data_schema"]({}) == {CONF_PERSISTENT_CONNECTION: False}
    with patch.object(
        hass.config_entries, "async_reload", new_callable=AsyncMock, return_value=True
    ) as reload:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_PERSISTENT_CONNECTION: persistent}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_entry.options == {CONF_PERSISTENT_CONNECTION: persistent}
    reload.assert_awaited_once_with(mock_entry.entry_id)


@pytest.mark.parametrize("persistent", [False, True])
async def test_setup_and_cleanup(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
    persistent: bool,
) -> None:
    """Setup forwards the option and unloading disconnects the client."""
    mock_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_entry, options={CONF_PERSISTENT_CONNECTION: persistent}
    )
    inject_bluetooth_service_info(hass, WATER_TIMER_SERVICE_INFO)
    with patch(
        "homeassistant.components.gardena_bluetooth.get_connection",
        wraps=get_connection,
    ) as connection:
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
    connection.assert_called_with(hass, WATER_TIMER_SERVICE_INFO.address, persistent)
    await hass.config_entries.async_unload(mock_entry.entry_id)
    await hass.async_block_till_done()
    mock_client.disconnect.assert_awaited_once()
