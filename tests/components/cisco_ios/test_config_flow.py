"""Test the Cisco IOS config flow."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from pexpect import pxssh

from homeassistant.components.cisco_ios.const import DOMAIN
from homeassistant.components.device_tracker import CONF_CONSIDER_HOME
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_CONFIG, MOCK_HOST

from tests.common import MockConfigEntry

MOCK_IMPORT_DATA = {**MOCK_CONFIG, CONF_CONSIDER_HOME: 240}


async def test_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_scanner: MagicMock
) -> None:
    """Test the full user flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Cisco IOS ({MOCK_HOST})"
    assert result["data"] == MOCK_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect_recovers(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_scanner: MagicMock
) -> None:
    """Test the user flow recovers from a connection error."""
    mock_scanner.return_value.get_devices.side_effect = pxssh.ExceptionPxssh("fail")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_scanner.return_value.get_devices.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Cisco IOS ({MOCK_HOST})"


async def test_form_duplicate_aborts(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_scanner: MagicMock
) -> None:
    """Test the user flow aborts when the host is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_scanner: MagicMock
) -> None:
    """Test the import flow creates an entry with the consider_home option."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data={**MOCK_IMPORT_DATA}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Cisco IOS ({MOCK_HOST})"
    assert result["data"] == MOCK_CONFIG
    assert result["options"] == {CONF_CONSIDER_HOME: 240}


async def test_import_cannot_connect(
    hass: HomeAssistant, mock_scanner: MagicMock
) -> None:
    """Test the import flow aborts when the router is unreachable."""
    mock_scanner.return_value.get_devices.side_effect = pxssh.ExceptionPxssh("fail")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data={**MOCK_IMPORT_DATA}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_import_duplicate_aborts(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_scanner: MagicMock
) -> None:
    """Test the import flow aborts when the host is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data={**MOCK_IMPORT_DATA}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_scanner: MagicMock
) -> None:
    """Test the options flow updates the consider_home option."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_CONSIDER_HOME: 300},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {CONF_CONSIDER_HOME: 300}
    # The entry is reloaded, so the new value is applied to the coordinator
    assert mock_config_entry.runtime_data.consider_home == timedelta(seconds=300)


async def test_import_preserves_large_consider_home(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_scanner: MagicMock
) -> None:
    """Test the import flow preserves values above the options flow maximum."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={**MOCK_CONFIG, CONF_CONSIDER_HOME: 1800},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {CONF_CONSIDER_HOME: 1800}
