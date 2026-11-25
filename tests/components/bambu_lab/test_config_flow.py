"""Tests for the Bambu Lab config flow."""

from unittest.mock import AsyncMock, MagicMock

from aiobambulab import (
    BambuLabAuthenticationError,
    BambuLabCertificateError,
    BambuLabConnectionError,
    BambuLabSerialMismatchError,
    PrinterInfo,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.bambu_lab.const import (
    CONF_ACCESS_CODE,
    CONF_SERIAL_NUMBER,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import ACCESS_CODE, HOST, SERIAL_NUMBER

USER_INPUT = {
    CONF_HOST: HOST,
    CONF_SERIAL_NUMBER: SERIAL_NUMBER,
    CONF_ACCESS_CODE: ACCESS_CODE,
}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_flow(
    hass: HomeAssistant,
    mock_bambu_lab_client_class: MagicMock,
    mock_bambu_lab_client: MagicMock,
) -> None:
    """Test the full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "X1 Carbon"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == SERIAL_NUMBER
    mock_bambu_lab_client_class.assert_called_once_with(
        HOST, SERIAL_NUMBER, ACCESS_CODE
    )
    mock_bambu_lab_client.connect.assert_awaited_once()
    mock_bambu_lab_client.disconnect.assert_awaited_once()


@pytest.mark.usefixtures("mock_setup_entry", "mock_bambu_lab_client")
async def test_flow_with_serial_number_in_lower_case(
    hass: HomeAssistant, mock_bambu_lab_client_class: MagicMock
) -> None:
    """Test the entry gets the serial number as the printer writes it."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_SERIAL_NUMBER: SERIAL_NUMBER.lower()}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == SERIAL_NUMBER
    mock_bambu_lab_client_class.assert_called_once_with(
        HOST, SERIAL_NUMBER.lower(), ACCESS_CODE
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_flow_with_unknown_model(
    hass: HomeAssistant, mock_bambu_lab_client: MagicMock
) -> None:
    """Test the entry is named after the serial number of an unknown printer."""
    mock_bambu_lab_client.info = PrinterInfo(serial=SERIAL_NUMBER)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == SERIAL_NUMBER
    assert result["result"].unique_id == SERIAL_NUMBER


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        pytest.param(BambuLabAuthenticationError, "invalid_auth", id="invalid_auth"),
        pytest.param(
            BambuLabSerialMismatchError,
            "serial_number_mismatch",
            id="serial_number_mismatch",
        ),
        pytest.param(
            BambuLabCertificateError,
            "untrusted_certificate",
            id="untrusted_certificate",
        ),
        pytest.param(BambuLabConnectionError, "cannot_connect", id="cannot_connect"),
        pytest.param(Exception, "unknown", id="unknown"),
    ],
)
async def test_flow_errors(
    hass: HomeAssistant,
    mock_bambu_lab_client: MagicMock,
    mock_setup_entry: AsyncMock,
    exception: type[Exception],
    error: str,
) -> None:
    """Test the flow shows an error, and recovers from it."""
    mock_bambu_lab_client.connect.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    mock_bambu_lab_client.connect.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == SERIAL_NUMBER
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_bambu_lab_client")
async def test_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the flow aborts for a printer that is already set up."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_HOST: "192.168.1.51"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == HOST


@pytest.mark.usefixtures("mock_setup_entry")
async def test_flow_while_another_shows_an_error(
    hass: HomeAssistant, mock_bambu_lab_client: MagicMock
) -> None:
    """Test a flow that shows an error does not block another for the printer."""
    first_flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    second_flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_bambu_lab_client.connect.side_effect = BambuLabConnectionError

    result = await hass.config_entries.flow.async_configure(
        first_flow["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_bambu_lab_client.connect.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        second_flow["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == SERIAL_NUMBER

    result = await hass.config_entries.flow.async_configure(
        first_flow["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
