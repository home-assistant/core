"""Test the La Marzocco config flow."""
from unittest.mock import MagicMock

from lmcloud.exceptions import AuthFail, RequestNotSuccessful

from homeassistant import config_entries
from homeassistant.components.lamarzocco.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    DEFAULT_CONF,
    DISCOVERED_INFO,
    LM_SERVICE_INFO,
    LOGIN_INFO,
    MACHINE_DATA,
    MACHINE_SELECTION,
    OPTIONS_INPUT,
    USER_INPUT,
    WRONG_LOGIN_INFO,
)

from tests.common import MockConfigEntry


async def test_show_config_form(hass: HomeAssistant) -> None:
    """Test if initial configuration form is shown."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_form(hass: HomeAssistant, mock_lamarzocco: MagicMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "machine_selection"

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        MACHINE_SELECTION,
    )
    await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY

    assert result3["title"] == "GS3 AV"
    assert result3["data"] == USER_INPUT | DEFAULT_CONF | MACHINE_DATA

    assert len(mock_lamarzocco.check_local_connection.mock_calls) == 1

    # test abort if already configured
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "machine_selection"

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        MACHINE_SELECTION,
    )
    await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.ABORT

    assert result3["reason"] == "already_configured"

    assert len(mock_lamarzocco.check_local_connection.mock_calls) == 1


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_lamarzocco: MagicMock
) -> None:
    """Test invalid auth error."""

    mock_lamarzocco.get_all_machines.side_effect = AuthFail("")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}
    assert len(mock_lamarzocco.get_all_machines.mock_calls) == 1


async def test_form_invalid_host(
    hass: HomeAssistant, mock_lamarzocco: MagicMock
) -> None:
    """Test invalid auth error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    await hass.async_block_till_done()

    mock_lamarzocco.check_local_connection.return_value = False

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "machine_selection"

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        MACHINE_SELECTION,
    )
    await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"host": "cannot_connect"}
    assert len(mock_lamarzocco.get_all_machines.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_lamarzocco: MagicMock
) -> None:
    """Test cannot connect error."""

    mock_lamarzocco.get_all_machines.side_effect = RequestNotSuccessful("")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
    assert len(mock_lamarzocco.get_all_machines.mock_calls) == 1


async def test_bluetooth_discovery(
    hass: HomeAssistant, mock_lamarzocco: MagicMock
) -> None:
    """Test bluetooth discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=LM_SERVICE_INFO,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "machine_selection"

    assert len(mock_lamarzocco.get_all_machines.mock_calls) == 1
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        MACHINE_SELECTION,
    )
    await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY

    assert result3["title"] == "GS3 AV"
    assert result3["data"] == USER_INPUT | DEFAULT_CONF | MACHINE_DATA | DISCOVERED_INFO

    assert len(mock_lamarzocco.check_local_connection.mock_calls) == 1


async def test_show_reauth(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that the reauth form shows."""

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": mock_config_entry.unique_id,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"


async def test_reauth_flow(
    hass: HomeAssistant, mock_lamarzocco: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test that the reauth flow."""

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": mock_config_entry.unique_id,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        LOGIN_INFO,
    )

    assert result2["type"] == FlowResultType.ABORT
    await hass.async_block_till_done()
    assert result2["reason"] == "reauth_successful"
    assert len(mock_lamarzocco.get_all_machines.mock_calls) == 1


async def test_reauth_errors(
    hass: HomeAssistant, mock_lamarzocco: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test the reauth flow errors."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": mock_config_entry.unique_id,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )

    mock_lamarzocco.get_all_machines.side_effect = AuthFail("")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        WRONG_LOGIN_INFO,
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}

    assert len(mock_lamarzocco.get_all_machines.mock_calls) == 1

    mock_lamarzocco.get_all_machines.side_effect = RequestNotSuccessful("")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        LOGIN_INFO,
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    assert len(mock_lamarzocco.get_all_machines.mock_calls) == 2


async def test_options_flow(
    hass: HomeAssistant, mock_lamarzocco: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test options flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=OPTIONS_INPUT
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == OPTIONS_INPUT


async def test_options_flow_errors(
    hass: HomeAssistant, mock_lamarzocco: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test options flow errors."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    mock_lamarzocco.check_local_connection.return_value = False

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=OPTIONS_INPUT
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"host": "cannot_connect"}
