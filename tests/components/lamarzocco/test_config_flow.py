"""Test the La Marzocco config flow."""
import pytest

from unittest.mock import MagicMock

from lmcloud.exceptions import AuthFail, RequestNotSuccessful

from homeassistant import config_entries
from homeassistant.components.lamarzocco.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    DISCOVERED_INFO,
    HOST_SELECTION,
    LM_SERVICE_INFO,
    LOGIN_INFO,
    MACHINE_DATA,
    MACHINE_SELECTION,
    USER_INPUT,
    WRONG_LOGIN_INFO,
)

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant, mock_lamarzocco: MagicMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"

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

    assert result3["title"] == "GS01234"
    assert result3["data"] == USER_INPUT | MACHINE_DATA

    assert len(mock_lamarzocco.check_local_connection.mock_calls) == 1


async def test_form_abort_already_configured(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort if already configured."""
    mock_config_entry.add_to_hass(hass)

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

    mock_lamarzocco.get_all_machines.return_value = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "no_machines"}
    assert len(mock_lamarzocco.get_all_machines.mock_calls) == 1

    mock_lamarzocco.get_all_machines.side_effect = RequestNotSuccessful("")
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
    assert len(mock_lamarzocco.get_all_machines.mock_calls) == 2


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
    assert result2["step_id"] == "host_selection"

    assert len(mock_lamarzocco.get_all_machines.mock_calls) == 1
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        HOST_SELECTION,
    )
    await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY

    assert result3["title"] == "GS01234"
    assert result3["data"] == USER_INPUT | MACHINE_DATA | DISCOVERED_INFO

    assert len(mock_lamarzocco.check_local_connection.mock_calls) == 1


async def test_bluetooth_discovery_errors(
    hass: HomeAssistant, mock_lamarzocco: MagicMock
) -> None:
    """Test bluetooth discovery errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=LM_SERVICE_INFO,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_lamarzocco.get_all_machines.return_value = [("GS98765", "GS3 MP")]
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "machine_not_found"}
    assert len(mock_lamarzocco.get_all_machines.mock_calls) == 1

    mock_lamarzocco.get_all_machines.return_value = [("GS01234", "GS3 AV")]
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "host_selection"
    assert len(mock_lamarzocco.get_all_machines.mock_calls) == 2

    mock_lamarzocco.check_local_connection.return_value = False
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        HOST_SELECTION,
    )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"host": "cannot_connect"}

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


async def test_no_machines(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test no machines."""
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

    mock_lamarzocco.get_all_machines.return_value = []

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        WRONG_LOGIN_INFO,
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "no_machines"}

    assert len(mock_lamarzocco.get_all_machines.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (AuthFail(""), "invalid_auth"),
        (RequestNotSuccessful(""), "cannot_connect"),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    reason: str,
) -> None:
    """Test the reauth errors."""
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
    mock_lamarzocco.get_all_machines.side_effect = side_effect

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        WRONG_LOGIN_INFO,
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": reason}

    assert len(mock_lamarzocco.get_all_machines.mock_calls) == 1
