"""Configuration flow tests for the Zendure integration."""

import logging
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from zendure import UnsupportedDeviceError, ValidationError, ZendureConnectionError

from homeassistant.components.zendure.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import SERIAL_NUMBER

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.mark.usefixtures("mock_zendure")
async def test_user_flow(hass: HomeAssistant) -> None:
    """Test the full happy path user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.50"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "SolarFlow 2400 AC+"
    assert result["data"] == {CONF_HOST: "192.168.1.50"}
    assert result["result"].unique_id == SERIAL_NUMBER


@pytest.mark.usefixtures("mock_zendure")
@pytest.mark.parametrize(
    ("side_effect", "field", "error"),
    [
        (ZendureConnectionError, "base", "cannot_connect"),
        (UnsupportedDeviceError("someModel"), "base", "unsupported_device"),
        (ValidationError, CONF_HOST, "invalid_host"),
        (Exception, "base", "unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_read: AsyncMock,
    side_effect: Exception,
    field: str,
    error: str,
) -> None:
    """Test we show user form on an error and recover from it."""
    mock_read.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "192.168.1.50"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {field: error}

    mock_read.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.50"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_zendure")
async def test_unsupported_product_is_logged(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, mock_read: AsyncMock
) -> None:
    """Test the product string the device reports is logged when unsupported."""
    mock_read.side_effect = UnsupportedDeviceError("solarFlowNewModel")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with caplog.at_level(logging.DEBUG, logger="homeassistant.components.zendure"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: "192.168.1.50"}
        )

    assert result["errors"] == {"base": "unsupported_device"}
    assert (
        "Device at 192.168.1.50 reports unsupported product 'solarFlowNewModel'"
        in caplog.text
    )

    mock_read.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.50"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == SERIAL_NUMBER


@pytest.mark.usefixtures("mock_zendure")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test configuring the same device twice updates its address."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "192.168.1.99"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.99"
