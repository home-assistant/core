"""Test the Hue BLE config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.components.hue_ble.config_flow import (
    CannotConnect,
    InvalidAuth,
    NotFound,
    ScannerNotAvaliable,
)
from homeassistant.components.hue_ble.const import DOMAIN
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: "Name of the device", CONF_MAC: "aa:bb:cc:dd:ee:ff"},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Name of the device"
    assert result["data"] == {
        CONF_NAME: "Name of the device",
        CONF_MAC: "aa:bb:cc:dd:ee:ff",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle when we cannot connect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: "Name of the device", CONF_MAC: "aa:bb:cc:dd:ee:ff"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: "Name of the device", CONF_MAC: "aa:bb:cc:dd:ee:ff"},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Name of the device"
    assert result["data"] == {
        CONF_NAME: "Name of the device",
        CONF_MAC: "aa:bb:cc:dd:ee:ff",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_not_authenticated(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle not being authenticated."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        side_effect=InvalidAuth,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: "Name of the device", CONF_MAC: "aa:bb:cc:dd:ee:ff"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: "Name of the device", CONF_MAC: "aa:bb:cc:dd:ee:ff"},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Name of the device"
    assert result["data"] == {
        CONF_NAME: "Name of the device",
        CONF_MAC: "aa:bb:cc:dd:ee:ff",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_no_scanners(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle no scanners."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        side_effect=ScannerNotAvaliable,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: "Name of the device", CONF_MAC: "aa:bb:cc:dd:ee:ff"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "no_scanners"}

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: "Name of the device", CONF_MAC: "aa:bb:cc:dd:ee:ff"},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Name of the device"
    assert result["data"] == {
        CONF_NAME: "Name of the device",
        CONF_MAC: "aa:bb:cc:dd:ee:ff",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_not_found(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we handle light not found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        side_effect=NotFound,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: "Name of the device", CONF_MAC: "aa:bb:cc:dd:ee:ff"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "not_found"}

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: "Name of the device", CONF_MAC: "aa:bb:cc:dd:ee:ff"},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Name of the device"
    assert result["data"] == {
        CONF_NAME: "Name of the device",
        CONF_MAC: "aa:bb:cc:dd:ee:ff",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_unknown(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we handle an unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: "Name of the device", CONF_MAC: "aa:bb:cc:dd:ee:ff"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: "Name of the device", CONF_MAC: "aa:bb:cc:dd:ee:ff"},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Name of the device"
    assert result["data"] == {
        CONF_NAME: "Name of the device",
        CONF_MAC: "aa:bb:cc:dd:ee:ff",
    }
    assert len(mock_setup_entry.mock_calls) == 1
