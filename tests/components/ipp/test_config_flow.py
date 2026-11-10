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
    IPPResponseError,
    IPPVersionNotSupportedError,
    Printer,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, load_fixture

from homeassistant.components.ipp.const import CONF_BASE_PATH, DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SSL,
    CONF_UUID,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr

from . import (
    MOCK_USER_INPUT,
    MOCK_ZEROCONF_IPP_SERVICE_INFO,
    MOCK_ZEROCONF_IPPS_SERVICE_INFO,
)

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_show_user_form(hass: HomeAssistant) -> None:
    """Test that the user set up form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM


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
    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"] == {CONF_NAME: "EPSON XP-6000 Series"}


async def test_connection_error(
    hass: HomeAssistant,
    mock_ipp_config_flow: MagicMock,
) -> None:
    """Test we show user form on IPP connection error."""
    mock_ipp_config_flow.printer.side_effect = IPPConnectionError

    user_input = MOCK_USER_INPUT.copy()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_ipp_config_flow.printer.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


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

    assert result["type"] is FlowResultType.ABORT
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

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_user_connection_upgrade_required(
    hass: HomeAssistant,
    mock_ipp_config_flow: MagicMock,
) -> None:
    """Test we show the user form if connection upgrade required by server."""
    mock_ipp_config_flow.printer.side_effect = IPPConnectionUpgradeRequired

    user_input = MOCK_USER_INPUT.copy()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "connection_upgrade"}

    mock_ipp_config_flow.printer.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


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

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "connection_upgrade"


async def test_user_parse_error(
    hass: HomeAssistant,
    mock_ipp_config_flow: MagicMock,
) -> None:
    """Test we abort user flow on IPP parse error."""
    mock_ipp_config_flow.printer.side_effect = IPPParseError

    user_input = MOCK_USER_INPUT.copy()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] is FlowResultType.ABORT
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

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "parse_error"


async def test_user_ipp_error(
    hass: HomeAssistant,
    mock_ipp_config_flow: MagicMock,
) -> None:
    """Test we abort the user flow on IPP error."""
    mock_ipp_config_flow.printer.side_effect = IPPError

    user_input = MOCK_USER_INPUT.copy()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] is FlowResultType.ABORT
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

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "ipp_error"


async def test_user_ipp_version_error(
    hass: HomeAssistant,
    mock_ipp_config_flow: MagicMock,
) -> None:
    """Test we abort user flow on IPP version not supported error."""
    mock_ipp_config_flow.printer.side_effect = IPPVersionNotSupportedError

    user_input = {**MOCK_USER_INPUT}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] is FlowResultType.ABORT
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

    assert result["type"] is FlowResultType.ABORT
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
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] is FlowResultType.ABORT
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

    assert result["type"] is FlowResultType.ABORT
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

    assert result["type"] is FlowResultType.ABORT
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

    assert result["type"] is FlowResultType.ABORT
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

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.31", CONF_BASE_PATH: "/ipp/print"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
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

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.31", CONF_BASE_PATH: "/ipp/print"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
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
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.31", CONF_BASE_PATH: "/ipp/print"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
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
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
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
    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"] == {CONF_NAME: "EPSON XP-6000 Series"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "EPSON XP-6000 Series"

    assert result["data"]
    assert result["data"][CONF_HOST] == "192.168.1.31"
    assert result["data"][CONF_NAME] == "EPSON XP-6000 Series"
    assert result["data"][CONF_UUID] == "cfe92100-67c4-11d4-a45f-f8d027761251"
    assert result["data"][CONF_SSL]

    assert result["result"]
    assert result["result"].unique_id == "cfe92100-67c4-11d4-a45f-f8d027761251"


async def test_zeroconf_empty_unique_id_uses_serial(hass: HomeAssistant) -> None:
    """Test zeroconf flow with empty unique ID uses serial fallback."""
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

        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.31", CONF_BASE_PATH: "/ipp/print"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "EPSON XP-6000 Series"

    assert result["data"]
    assert result["data"][CONF_HOST] == "192.168.1.31"
    assert result["data"][CONF_UUID] == ""

    assert result["result"]
    assert result["result"].unique_id == "555534593035345555"


RECONFIGURE_INPUT = {
    CONF_HOST: "192.168.1.32",
    CONF_PORT: 632,
    CONF_SSL: True,
    CONF_VERIFY_SSL: False,
    CONF_BASE_PATH: "/ipp/printer",
}


@pytest.mark.usefixtures("mock_ipp_config_flow")
async def test_reconfigure_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=RECONFIGURE_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        **RECONFIGURE_INPUT,
        CONF_UUID: "cfe92100-67c4-11d4-a45f-f8d027761251",
    }


@pytest.mark.parametrize(
    "mock_printer", ["ipp/printer_without_uuid.json"], indirect=True
)
@pytest.mark.usefixtures("mock_ipp_config_flow")
async def test_reconfigure_different_device(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfiguring to a different printer aborts."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=RECONFIGURE_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "different_device"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.31"


@pytest.mark.parametrize(
    "mock_printer", ["ipp/printer_without_uuid.json"], indirect=True
)
@pytest.mark.usefixtures("mock_ipp_config_flow")
async def test_reconfigure_zeroconf_uuid_matching_device_serial(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguring a printer whose zeroconf UUID is not reported over IPP."""
    mock_config_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "cfe92100-67c4-11d4-a45f-f8d027761251")},
        serial_number="555534593035345555",
    )

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=RECONFIGURE_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.32"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(
            IPPConnectionUpgradeRequired, "connection_upgrade", id="upgrade_required"
        ),
        pytest.param(IPPConnectionError, "cannot_connect", id="cannot_connect"),
        pytest.param(IPPResponseError, "cannot_connect", id="response_error"),
        pytest.param(
            IPPVersionNotSupportedError, "ipp_version_error", id="version_error"
        ),
        pytest.param(IPPParseError, "ipp_error", id="parse_error"),
        pytest.param(IPPError, "ipp_error", id="ipp_error"),
    ],
)
async def test_reconfigure_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ipp_config_flow: MagicMock,
    side_effect: type[Exception],
    error: str,
) -> None:
    """Test the reconfigure flow shows errors and can recover."""
    mock_config_entry.add_to_hass(hass)
    mock_ipp_config_flow.printer.side_effect = side_effect

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=RECONFIGURE_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": error}

    mock_ipp_config_flow.printer.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=RECONFIGURE_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.32"
