"""Tests for the IPP config flow."""
import dataclasses
from ipaddress import ip_address
import json
from unittest.mock import MagicMock, patch

from pyipp import (
    IPPConnectionError,
    IPPConnectionUpgradeRequired,
    IPPError,
    IPPParseError,
    IPPVersionNotSupportedError,
    Printer,
)
import pytest

from homeassistant.components.ipp.const import CONF_BASE_PATH, DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_SSL, CONF_UUID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    MOCK_USER_INPUT,
    MOCK_ZEROCONF_IPP_SERVICE_INFO,
    MOCK_ZEROCONF_IPPS_SERVICE_INFO,
)

from tests.common import MockConfigEntry, load_fixture

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_show_user_form(hass: HomeAssistant) -> None:
    """Test that the user set up form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] == FlowResultType.FORM


async def test_show_zeroconf_form(
    hass: HomeAssistant,
    mock_ipp_config_flow: MagicMock,
) -> None:
    """Test that the zeroconf confirmation form is served."""
    discovery_info = dataclasses.replace(MOCK_ZEROCONF_IPP_SERVICE_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] == FlowResultType.FORM
    assert result["description_placeholders"] == {CONF_NAME: "EPSON XP-6000 Series"}


async def test_connection_error(
    hass: HomeAssistant,
    mock_ipp_config_flow: MagicMock,
) -> None:
    """Test we show user form on IPP connection error."""
    mock_ipp_config_flow.printer.side_effect = IPPConnectionError

    user_input = MOCK_USER_INPUT.copy()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=user_input,
    )

    assert result["step_id"] == "user"
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_zeroconf_connection_error(
    hass: HomeAssistant,
    mock_ipp_config_flow: MagicMock,
) -> None:
    """Test we abort zeroconf flow on IPP connection error."""
    mock_ipp_config_flow.printer.side_effect = IPPConnectionError

    discovery_info = dataclasses.replace(MOCK_ZEROCONF_IPP_SERVICE_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_zeroconf_confirm_connection_error(
    hass: HomeAssistant,
    mock_ipp_config_flow: MagicMock,
) -> None:
    """Test we abort zeroconf flow on IPP connection error."""
    mock_ipp_config_flow.printer.side_effect = IPPConnectionError

    discovery_info = dataclasses.replace(MOCK_ZEROCONF_IPP_SERVICE_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery_info
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_user_connection_upgrade_required(
    hass: HomeAssistant,
    mock_ipp_config_flow: MagicMock,
) -> None:
    """Test we show the user form if connection upgrade required by server."""
    mock_ipp_config_flow.printer.side_effect = IPPConnectionUpgradeRequired

    user_input = MOCK_USER_INPUT.copy()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=user_input,
    )

    assert result["step_id"] == "user"
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "connection_upgrade"}


async def test_zeroconf_connection_upgrade_required(
    hass: HomeAssistant,
    mock_ipp_config_flow: MagicMock,
) -> None:
    """Test we abort zeroconf flow on IPP connection error."""
    mock_ipp_config_flow.printer.side_effect = IPPConnectionUpgradeRequired

    discovery_info = dataclasses.replace(MOCK_ZEROCONF_IPP_SERVICE_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "connection_upgrade"


async def test_user_parse_error(
    hass: HomeAssistant,
    mock_ipp_config_flow: MagicMock,
) -> None:
    """Test we abort user flow on IPP parse error."""
    mock_ipp_config_flow.printer.side_effect = IPPParseError

    user_input = MOCK_USER_INPUT.copy()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=user_input,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "parse_error"


async def test_zeroconf_parse_error(
    hass: HomeAssistant,
    mock_ipp_config_flow: MagicMock,
) -> None:
    """Test we abort zeroconf flow on IPP parse error."""
    mock_ipp_config_flow.printer.side_effect = IPPParseError

    discovery_info = dataclasses.replace(MOCK_ZEROCONF_IPP_SERVICE_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "parse_error"


async def test_user_ipp_error(
    hass: HomeAssistant,
    mock_ipp_config_flow: MagicMock,
) -> None:
    """Test we abort the user flow on IPP error."""
    mock_ipp_config_flow.printer.side_effect = IPPError

    user_input = MOCK_USER_INPUT.copy()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=user_input,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "ipp_error"


async def test_zeroconf_ipp_error(
    hass: HomeAssistant,
    mock_ipp_config_flow: MagicMock,
) -> None:
    """Test we abort zeroconf flow on IPP error."""
    mock_ipp_config_flow.printer.side_effect = IPPError

    discovery_info = dataclasses.replace(MOCK_ZEROCONF_IPP_SERVICE_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "ipp_error"


async def test_user_ipp_version_error(
    hass: HomeAssistant,
    mock_ipp_config_flow: MagicMock,
) -> None:
    """Test we abort user flow on IPP version not supported error."""
    mock_ipp_config_flow.printer.side_effect = IPPVersionNotSupportedError

    user_input = {**MOCK_USER_INPUT}
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=user_input,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "ipp_version_error"


async def test_zeroconf_ipp_version_error(
    hass: HomeAssistant,
    mock_ipp_config_flow: MagicMock,
) -> None:
    """Test we abort zeroconf flow on IPP version not supported error."""
    mock_ipp_config_flow.printer.side_effect = IPPVersionNotSupportedError

    discovery_info = dataclasses.replace(MOCK_ZEROCONF_IPP_SERVICE_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "ipp_version_error"


async def test_user_device_exists_abort(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ipp_config_flow: MagicMock,
) -> None:
    """Test we abort user flow if printer already configured."""
    mock_config_entry.add_to_hass(hass)

    user_input = MOCK_USER_INPUT.copy()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=user_input,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_device_exists_abort(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ipp_config_flow: MagicMock,
) -> None:
    """Test we abort zeroconf flow if printer already configured."""
    mock_config_entry.add_to_hass(hass)

    discovery_info = dataclasses.replace(MOCK_ZEROCONF_IPP_SERVICE_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_with_uuid_device_exists_abort(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ipp_config_flow: MagicMock,
) -> None:
    """Test we abort zeroconf flow if printer already configured."""
    mock_config_entry.add_to_hass(hass)

    discovery_info = dataclasses.replace(MOCK_ZEROCONF_IPP_SERVICE_INFO)
    discovery_info.properties = {
        **MOCK_ZEROCONF_IPP_SERVICE_INFO.properties,
        "UUID": "cfe92100-67c4-11d4-a45f-f8d027761251",
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_with_uuid_device_exists_abort_new_host(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ipp_config_flow: MagicMock,
) -> None:
    """Test we abort zeroconf flow if printer already configured."""
    mock_config_entry.add_to_hass(hass)

    discovery_info = dataclasses.replace(
        MOCK_ZEROCONF_IPP_SERVICE_INFO, ip_address=ip_address("1.2.3.9")
    )
    discovery_info.properties = {
        **MOCK_ZEROCONF_IPP_SERVICE_INFO.properties,
        "UUID": "cfe92100-67c4-11d4-a45f-f8d027761251",
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "1.2.3.9"


async def test_zeroconf_empty_unique_id(
    hass: HomeAssistant,
    mock_ipp_config_flow: MagicMock,
) -> None:
    """Test zeroconf flow if printer lacks (empty) unique identification."""
    printer = mock_ipp_config_flow.printer.return_value
    printer.unique_id = None

    discovery_info = dataclasses.replace(MOCK_ZEROCONF_IPP_SERVICE_INFO)
    discovery_info.properties = {
        **MOCK_ZEROCONF_IPP_SERVICE_INFO.properties,
        "UUID": "",
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.31", CONF_BASE_PATH: "/ipp/print"},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "EPSON XP-6000 Series"

    assert result["data"]
    assert result["data"][CONF_HOST] == "192.168.1.31"
    assert result["data"][CONF_UUID] == "cfe92100-67c4-11d4-a45f-f8d027761251"

    assert result["result"]
    assert result["result"].unique_id == "cfe92100-67c4-11d4-a45f-f8d027761251"


async def test_zeroconf_no_unique_id(
    hass: HomeAssistant,
    mock_ipp_config_flow: MagicMock,
) -> None:
    """Test zeroconf flow if printer lacks unique identification."""
    printer = mock_ipp_config_flow.printer.return_value
    printer.unique_id = None

    discovery_info = dataclasses.replace(MOCK_ZEROCONF_IPP_SERVICE_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.31", CONF_BASE_PATH: "/ipp/print"},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "EPSON XP-6000 Series"

    assert result["data"]
    assert result["data"][CONF_HOST] == "192.168.1.31"
    assert result["data"][CONF_UUID] == "cfe92100-67c4-11d4-a45f-f8d027761251"

    assert result["result"]
    assert result["result"].unique_id == "cfe92100-67c4-11d4-a45f-f8d027761251"


async def test_full_user_flow_implementation(
    hass: HomeAssistant,
    mock_ipp_config_flow: MagicMock,
) -> None:
    """Test the full manual user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.31", CONF_BASE_PATH: "/ipp/print"},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "192.168.1.31"

    assert result["data"]
    assert result["data"][CONF_HOST] == "192.168.1.31"
    assert result["data"][CONF_UUID] == "cfe92100-67c4-11d4-a45f-f8d027761251"

    assert result["result"]
    assert result["result"].unique_id == "cfe92100-67c4-11d4-a45f-f8d027761251"


async def test_full_zeroconf_flow_implementation(
    hass: HomeAssistant,
    mock_ipp_config_flow: MagicMock,
) -> None:
    """Test the full manual user flow from start to finish."""
    discovery_info = dataclasses.replace(MOCK_ZEROCONF_IPP_SERVICE_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "EPSON XP-6000 Series"

    assert result["data"]
    assert result["data"][CONF_HOST] == "192.168.1.31"
    assert result["data"][CONF_NAME] == "EPSON XP-6000 Series"
    assert result["data"][CONF_UUID] == "cfe92100-67c4-11d4-a45f-f8d027761251"
    assert not result["data"][CONF_SSL]

    assert result["result"]
    assert result["result"].unique_id == "cfe92100-67c4-11d4-a45f-f8d027761251"


async def test_full_zeroconf_tls_flow_implementation(
    hass: HomeAssistant,
    mock_ipp_config_flow: MagicMock,
) -> None:
    """Test the full manual user flow from start to finish."""
    discovery_info = dataclasses.replace(MOCK_ZEROCONF_IPPS_SERVICE_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] == FlowResultType.FORM
    assert result["description_placeholders"] == {CONF_NAME: "EPSON XP-6000 Series"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "EPSON XP-6000 Series"

    assert result["data"]
    assert result["data"][CONF_HOST] == "192.168.1.31"
    assert result["data"][CONF_NAME] == "EPSON XP-6000 Series"
    assert result["data"][CONF_UUID] == "cfe92100-67c4-11d4-a45f-f8d027761251"
    assert result["data"][CONF_SSL]

    assert result["result"]
    assert result["result"].unique_id == "cfe92100-67c4-11d4-a45f-f8d027761251"


async def test_zeroconf_empty_unique_id_uses_serial(hass: HomeAssistant) -> None:
    """Test zeroconf flow if printer lacks (empty) unique identification with serial fallback."""
    fixture = await hass.async_add_executor_job(
        load_fixture, "ipp/printer_without_uuid.json"
    )
    mock_printer_without_uuid = Printer.from_dict(json.loads(fixture))
    mock_printer_without_uuid.unique_id = None

    discovery_info = dataclasses.replace(MOCK_ZEROCONF_IPP_SERVICE_INFO)
    discovery_info.properties = {
        **MOCK_ZEROCONF_IPP_SERVICE_INFO.properties,
        "UUID": "",
    }
    with patch(
        "homeassistant.components.ipp.config_flow.IPP", autospec=True
    ) as ipp_mock:
        client = ipp_mock.return_value
        client.printer.return_value = mock_printer_without_uuid
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data=discovery_info,
        )

        assert result["type"] == FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.31", CONF_BASE_PATH: "/ipp/print"},
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "EPSON XP-6000 Series"

    assert result["data"]
    assert result["data"][CONF_HOST] == "192.168.1.31"
    assert result["data"][CONF_UUID] == ""

    assert result["result"]
    assert result["result"].unique_id == "555534593035345555"
