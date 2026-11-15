"""Tests for the Bambu Lab config flow."""

from unittest.mock import AsyncMock, MagicMock

from aiobambulab import (
    BambuLabAuthenticationError,
    BambuLabCertificateError,
    BambuLabConnectionError,
    BambuLabSerialMismatchError,
    DiscoveredPrinter,
    PrinterInfo,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.bambu_lab.const import (
    CONF_ACCESS_CODE,
    CONF_SERIAL_NUMBER,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import ACCESS_CODE, HOST, SERIAL_NUMBER

USER_INPUT = {
    CONF_HOST: HOST,
    CONF_SERIAL_NUMBER: SERIAL_NUMBER,
    CONF_ACCESS_CODE: ACCESS_CODE,
}

OTHER_HOST = "192.168.1.51"
OTHER_SERIAL_NUMBER = "01P00A000000002"

ERRORS = [
    pytest.param(BambuLabAuthenticationError, "invalid_auth", id="invalid_auth"),
    pytest.param(
        BambuLabSerialMismatchError,
        "serial_number_mismatch",
        id="serial_number_mismatch",
    ),
    pytest.param(
        BambuLabCertificateError, "untrusted_certificate", id="untrusted_certificate"
    ),
    pytest.param(BambuLabConnectionError, "cannot_connect", id="cannot_connect"),
    pytest.param(Exception, "unknown", id="unknown"),
]


async def start_flow(hass: HomeAssistant, next_step_id: str) -> ConfigFlowResult:
    """Start a flow, and choose how to find the printer."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert result["menu_options"] == ["discover", "manual"]

    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": next_step_id}
    )


async def search(hass: HomeAssistant) -> ConfigFlowResult:
    """Start a flow, search for printers, and return what comes after."""
    result = await start_flow(hass, "discover")
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "discover"
    assert result["progress_action"] == "discover"

    await hass.async_block_till_done()
    return await hass.config_entries.flow.async_configure(result["flow_id"])


@pytest.mark.usefixtures("mock_setup_entry")
async def test_manual_flow(
    hass: HomeAssistant,
    mock_bambu_lab_client_class: MagicMock,
    mock_bambu_lab_client: MagicMock,
) -> None:
    """Test setting up a printer by entering its details."""
    result = await start_flow(hass, "manual")
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
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
async def test_manual_flow_with_serial_number_in_lower_case(
    hass: HomeAssistant, mock_bambu_lab_client_class: MagicMock
) -> None:
    """Test the entry gets the serial number as the printer writes it."""
    result = await start_flow(hass, "manual")
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
async def test_manual_flow_with_unknown_model(
    hass: HomeAssistant, mock_bambu_lab_client: MagicMock
) -> None:
    """Test the entry is named after the serial number of an unknown printer."""
    mock_bambu_lab_client.info = PrinterInfo(serial=SERIAL_NUMBER)

    result = await start_flow(hass, "manual")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == SERIAL_NUMBER
    assert result["result"].unique_id == SERIAL_NUMBER


@pytest.mark.parametrize(("exception", "error"), ERRORS)
async def test_manual_flow_errors(
    hass: HomeAssistant,
    mock_bambu_lab_client: MagicMock,
    mock_setup_entry: AsyncMock,
    exception: type[Exception],
    error: str,
) -> None:
    """Test the flow shows an error, and recovers from it."""
    mock_bambu_lab_client.connect.side_effect = exception

    result = await start_flow(hass, "manual")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
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
async def test_manual_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the flow aborts for a printer that is already set up."""
    mock_config_entry.add_to_hass(hass)

    result = await start_flow(hass, "manual")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_HOST: OTHER_HOST}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == HOST


@pytest.mark.usefixtures("mock_setup_entry")
async def test_flow_while_another_shows_an_error(
    hass: HomeAssistant, mock_bambu_lab_client: MagicMock
) -> None:
    """Test a flow that shows an error does not block another for the printer."""
    first_flow = await start_flow(hass, "manual")
    second_flow = await start_flow(hass, "manual")

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


@pytest.mark.usefixtures("mock_setup_entry", "mock_discover", "mock_bambu_lab_client")
async def test_discovery_flow(
    hass: HomeAssistant, mock_bambu_lab_client_class: MagicMock
) -> None:
    """Test setting up the only printer that was found."""
    result = await search(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "access_code"
    assert result["description_placeholders"] == {"name": "3DP-01P-001", "host": HOST}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_CODE: ACCESS_CODE}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "X1 Carbon"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == SERIAL_NUMBER
    mock_bambu_lab_client_class.assert_called_once_with(
        HOST, SERIAL_NUMBER, ACCESS_CODE
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_discovery_flow_with_several_printers(
    hass: HomeAssistant,
    mock_discover: AsyncMock,
    mock_bambu_lab_client_class: MagicMock,
    mock_bambu_lab_client: MagicMock,
) -> None:
    """Test picking one of the printers that were found."""
    mock_discover.return_value = [
        DiscoveredPrinter(serial=SERIAL_NUMBER, host=HOST, name="3DP-01P-001"),
        DiscoveredPrinter(serial=OTHER_SERIAL_NUMBER, host=OTHER_HOST),
    ]
    mock_bambu_lab_client.serial = OTHER_SERIAL_NUMBER

    result = await search(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_printer"
    assert result["data_schema"].schema[CONF_SERIAL_NUMBER].config["options"] == [
        {"value": SERIAL_NUMBER, "label": f"3DP-01P-001 ({HOST})"},
        {
            "value": OTHER_SERIAL_NUMBER,
            "label": f"{OTHER_SERIAL_NUMBER} ({OTHER_HOST})",
        },
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SERIAL_NUMBER: OTHER_SERIAL_NUMBER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "access_code"
    assert result["description_placeholders"] == {
        "name": OTHER_SERIAL_NUMBER,
        "host": OTHER_HOST,
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_CODE: ACCESS_CODE}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: OTHER_HOST,
        CONF_SERIAL_NUMBER: OTHER_SERIAL_NUMBER,
        CONF_ACCESS_CODE: ACCESS_CODE,
    }
    assert result["result"].unique_id == OTHER_SERIAL_NUMBER
    mock_bambu_lab_client_class.assert_called_once_with(
        OTHER_HOST, OTHER_SERIAL_NUMBER, ACCESS_CODE
    )


@pytest.mark.parametrize(("exception", "error"), ERRORS)
@pytest.mark.usefixtures("mock_discover")
async def test_discovery_flow_errors(
    hass: HomeAssistant,
    mock_bambu_lab_client: MagicMock,
    mock_setup_entry: AsyncMock,
    exception: type[Exception],
    error: str,
) -> None:
    """Test the flow shows an error for the access code, and recovers from it."""
    mock_bambu_lab_client.connect.side_effect = exception

    result = await search(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_CODE: ACCESS_CODE}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "access_code"
    assert result["errors"] == {"base": error}

    mock_bambu_lab_client.connect.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_CODE: ACCESS_CODE}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == SERIAL_NUMBER
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "found",
    [
        pytest.param({"return_value": []}, id="no_printers"),
        pytest.param({"side_effect": BambuLabConnectionError}, id="cannot_listen"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry", "mock_bambu_lab_client")
async def test_discovery_flow_without_printers(
    hass: HomeAssistant, mock_discover: AsyncMock, found: dict[str, object]
) -> None:
    """Test the flow asks for the details when the search finds nothing."""
    mock_discover.configure_mock(**found)

    result = await search(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    assert result["errors"] == {"base": "no_printers_found"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == SERIAL_NUMBER


@pytest.mark.usefixtures("mock_setup_entry", "mock_discover")
async def test_discovery_flow_skips_configured_printers(
    hass: HomeAssistant,
    mock_bambu_lab_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the search does not offer a printer that is already set up."""
    mock_config_entry.add_to_hass(hass)
    mock_bambu_lab_client.serial = OTHER_SERIAL_NUMBER

    result = await search(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    assert result["errors"] == {"base": "no_printers_found"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: OTHER_HOST,
            CONF_SERIAL_NUMBER: OTHER_SERIAL_NUMBER,
            CONF_ACCESS_CODE: ACCESS_CODE,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == OTHER_SERIAL_NUMBER
