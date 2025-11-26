"""Test the IntelliClima config flow."""

from unittest.mock import AsyncMock

from pyintelliclima.api import (
    IntelliClimaAPIError,
    IntelliClimaAuthError,
    IntelliClimaDevices,
)

from homeassistant import config_entries
from homeassistant.components.intelliclima.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

DATA_CONFIG = {
    CONF_USERNAME: "SuperUser",
    CONF_PASSWORD: "hunter2",
}


async def test_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_cloud_interface
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        DATA_CONFIG,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "IntelliClima (SuperUser)"
    assert result["data"] == DATA_CONFIG


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_cloud_interface
) -> None:
    """Test we handle invalid auth."""
    mock_cloud_interface.authenticate.side_effect = IntelliClimaAuthError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        DATA_CONFIG,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    # Erase the error
    mock_cloud_interface.authenticate.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        DATA_CONFIG,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "IntelliClima (SuperUser)"
    assert result["data"] == DATA_CONFIG


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_cloud_interface
) -> None:
    """Test we handle cannot connect error."""
    mock_cloud_interface.authenticate.side_effect = IntelliClimaAPIError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        DATA_CONFIG,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    # Erase the error
    mock_cloud_interface.authenticate.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        DATA_CONFIG,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "IntelliClima (SuperUser)"
    assert result["data"] == DATA_CONFIG


async def test_form_no_devices(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_cloud_interface,
    single_eco_device,
) -> None:
    """Test we handle no devices found error."""
    # Return empty devices list
    mock_cloud_interface.get_all_device_status.return_value = IntelliClimaDevices(
        ecocomfort2={}, c800={}
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        DATA_CONFIG,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_devices"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    # Reset to return devices on retry

    # Reset the return_value to its default state
    mock_cloud_interface.get_all_device_status.return_value = single_eco_device

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        DATA_CONFIG,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "IntelliClima (SuperUser)"
    assert result["data"] == DATA_CONFIG


async def test_form_unknown_error(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_cloud_interface
) -> None:
    """Test we handle unknown errors."""
    mock_cloud_interface.authenticate.side_effect = RuntimeError("Unexpected error")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        DATA_CONFIG,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    # Erase the error
    mock_cloud_interface.authenticate.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        DATA_CONFIG,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "IntelliClima (SuperUser)"
    assert result["data"] == DATA_CONFIG
