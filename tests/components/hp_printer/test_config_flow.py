"""Test the HP Printer config flow."""

from dataclasses import replace
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

from homeassistant.components.hp_printer.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import HOST, SERIAL_NUMBER, TITLE

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow(hass: HomeAssistant, mock_hp_printer: AsyncMock) -> None:
    """Test the full user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == {CONF_HOST: HOST}
    assert result["result"].unique_id == SERIAL_NUMBER


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
        result["flow_id"], {CONF_HOST: HOST}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(HpPrinterConnectionError, id="connection"),
        pytest.param(HpPrinterTimeoutError, id="timeout"),
        pytest.param(HpPrinterHttpError(404, "Not found"), id="http"),
        pytest.param(HpPrinterParseError, id="parse"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_cannot_connect(
    hass: HomeAssistant,
    mock_hp_printer: AsyncMock,
    exception: HpPrinterError,
) -> None:
    """Test the flow recovers after the printer could not be reached."""
    mock_hp_printer.device.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_hp_printer.device.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


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
        result["flow_id"], {CONF_HOST: HOST}
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
        result["flow_id"], {CONF_HOST: HOST}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
