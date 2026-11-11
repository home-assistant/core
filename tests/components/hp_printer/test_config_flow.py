"""Test the HP Printer config flow."""

from dataclasses import replace
from ipaddress import ip_address
from unittest.mock import AsyncMock

from aiohpprinter import (
    HpPrinterConnectionError,
    HpPrinterDevice,
    HpPrinterError,
    HpPrinterHttpError,
    HpPrinterParseError,
    HpPrinterTimeoutError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.hp_printer.const import DOMAIN, SECTION_ADVANCED_SETTINGS
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .conftest import HOST, SERIAL_NUMBER, TITLE

USER_INPUT = {CONF_HOST: HOST, SECTION_ADVANCED_SETTINGS: {CONF_SSL: False}}

NEW_HOST = "192.168.1.13"

ZEROCONF_DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address(NEW_HOST),
    ip_addresses=[ip_address(NEW_HOST)],
    hostname="HPA1B2C3.local.",
    name="HP OfficeJet Pro 9020 series [A1B2C3]._ipp._tcp.local.",
    port=631,
    type="_ipp._tcp.local.",
    properties={},
)


@pytest.mark.usefixtures("mock_hp_printer")
async def test_user_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test the full user flow."""
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
    assert result["title"] == TITLE
    assert result["data"] == {CONF_HOST: HOST, CONF_SSL: False}
    assert result["result"].unique_id == SERIAL_NUMBER

    assert mock_setup_entry.call_count == 1


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_title_falls_back_to_host(
    hass: HomeAssistant,
    mock_hp_printer: AsyncMock,
    mock_device: HpPrinterDevice,
) -> None:
    """Test the entry is named after the host when the printer has no model."""
    mock_hp_printer.device.return_value = replace(mock_device, make_and_model=None)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST
    assert result["result"].unique_id == SERIAL_NUMBER


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(HpPrinterConnectionError, id="connection"),
        pytest.param(HpPrinterTimeoutError, id="timeout"),
        pytest.param(HpPrinterHttpError(404, "Not found"), id="http"),
        pytest.param(HpPrinterParseError, id="parse"),
    ],
)
@pytest.mark.parametrize("endpoint", ["device", "status"])
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_cannot_connect(
    hass: HomeAssistant,
    mock_hp_printer: AsyncMock,
    exception: HpPrinterError,
    endpoint: str,
) -> None:
    """Test the flow recovers after the printer could not be reached."""
    getattr(mock_hp_printer, endpoint).side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    getattr(mock_hp_printer, endpoint).side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == SERIAL_NUMBER


async def test_user_flow_missing_serial_number(
    hass: HomeAssistant,
    mock_hp_printer: AsyncMock,
    mock_device: HpPrinterDevice,
) -> None:
    """Test the flow aborts when the printer does not report a serial number."""
    mock_hp_printer.device.return_value = replace(mock_device, serial_number=None)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_serial_number"


@pytest.mark.usefixtures("mock_hp_printer")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the flow aborts when the printer is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_ssl_and_port(
    hass: HomeAssistant, mock_hp_printer: AsyncMock
) -> None:
    """Test the flow stores the advanced connection settings."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: HOST,
            SECTION_ADVANCED_SETTINGS: {CONF_SSL: True, CONF_PORT: 8443},
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: HOST, CONF_SSL: True, CONF_PORT: 8443}
    assert result["result"].unique_id == SERIAL_NUMBER


@pytest.mark.usefixtures("mock_hp_printer")
async def test_zeroconf_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test a printer discovered via zeroconf is added after confirmation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DISCOVERY
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == {CONF_HOST: NEW_HOST, CONF_SSL: False}
    assert result["result"].unique_id == SERIAL_NUMBER
    assert mock_setup_entry.call_count == 1


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_flow_title_falls_back_to_host(
    hass: HomeAssistant,
    mock_hp_printer: AsyncMock,
    mock_device: HpPrinterDevice,
) -> None:
    """Test a discovered printer is named after its host when it has no model."""
    mock_hp_printer.device.return_value = replace(mock_device, make_and_model=None)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DISCOVERY
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NEW_HOST
    assert result["result"].unique_id == SERIAL_NUMBER


@pytest.mark.parametrize(
    ("device_changes", "side_effect", "reason"),
    [
        pytest.param(
            {}, HpPrinterConnectionError, "cannot_connect", id="cannot_connect"
        ),
        pytest.param(
            {"serial_number": None}, None, "missing_serial_number", id="no_serial"
        ),
    ],
)
async def test_zeroconf_flow_abort(
    hass: HomeAssistant,
    mock_hp_printer: AsyncMock,
    mock_device: HpPrinterDevice,
    device_changes: dict[str, str | None],
    side_effect: type[HpPrinterError] | None,
    reason: str,
) -> None:
    """Test the zeroconf flow aborts when the printer cannot be identified."""
    mock_hp_printer.device.return_value = replace(mock_device, **device_changes)
    mock_hp_printer.device.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DISCOVERY
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_zeroconf_flow_updates_host(
    hass: HomeAssistant,
    mock_hp_printer: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test rediscovering a configured printer at a new host updates the entry."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DISCOVERY
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data == {CONF_HOST: NEW_HOST, CONF_SSL: False}


async def test_zeroconf_flow_known_host(
    hass: HomeAssistant,
    mock_hp_printer: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a printer at an already configured host is not probed again."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=replace(ZEROCONF_DISCOVERY, ip_address=ip_address(HOST)),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_hp_printer.device.assert_not_called()
