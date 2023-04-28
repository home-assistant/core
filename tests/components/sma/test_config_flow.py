"""Test the sma config flow."""
from unittest.mock import patch

from pysma.exceptions import (
    SmaAuthenticationException,
    SmaConnectionException,
    SmaReadException,
)

from homeassistant.components.sma.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_DEVICE, MOCK_USER_INPUT, _patch_async_setup_entry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch("pysma.SMA.new_session", return_value=True), patch(
        "pysma.SMA.device_info", return_value=MOCK_DEVICE
    ), _patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_USER_INPUT["host"]
    assert result["data"] == MOCK_USER_INPUT

    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "pysma.SMA.new_session", side_effect=SmaConnectionException
    ), _patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert len(mock_setup_entry.mock_calls) == 0


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "pysma.SMA.new_session", side_effect=SmaAuthenticationException
    ), _patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert len(mock_setup_entry.mock_calls) == 0


async def test_form_cannot_retrieve_device_info(hass: HomeAssistant) -> None:
    """Test we handle cannot retrieve device info error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch("pysma.SMA.new_session", return_value=True), patch(
        "pysma.SMA.read", side_effect=SmaReadException
    ), _patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_retrieve_device_info"}
    assert len(mock_setup_entry.mock_calls) == 0


async def test_form_unexpected_exception(hass: HomeAssistant) -> None:
    """Test we handle unexpected exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "pysma.SMA.new_session", side_effect=Exception
    ), _patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}
    assert len(mock_setup_entry.mock_calls) == 0


async def test_form_already_configured(hass: HomeAssistant, mock_config_entry) -> None:
    """Test starting a flow by user when already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch("pysma.SMA.new_session", return_value=True), patch(
        "pysma.SMA.device_info", return_value=MOCK_DEVICE
    ), patch(
        "pysma.SMA.close_session", return_value=True
    ), _patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(mock_setup_entry.mock_calls) == 0
