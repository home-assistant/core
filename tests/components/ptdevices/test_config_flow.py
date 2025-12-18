"""Test the PTDevices config flow."""

from unittest.mock import patch

from aioptdevices import (
    PTDevicesForbiddenError,
    PTDevicesRequestError,
    PTDevicesUnauthorizedError,
)
from aioptdevices.interface import PTDevicesResponse

from homeassistant.components.ptdevices.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_flow_success(
    hass: HomeAssistant,
    mock_ptdevices_level: PTDevicesResponse,
) -> None:
    """Test A successful creation of config entries via user configuration."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    with (
        patch(
            "aioptdevices.interface.Interface.get_data",
            return_value=mock_ptdevices_level,
        ),
        patch(
            "homeassistant.components.ptdevices.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_TOKEN: "test-api-token",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "User Name"
    assert result["data"] == {
        "api_token": "test-api-token",
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_flow_duplicate_device(
    hass: HomeAssistant,
    mock_ptdevices_level: PTDevicesResponse,
) -> None:
    """Test A successful creation of config entries via user configuration."""
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result1["type"] is FlowResultType.FORM
    assert result1["step_id"] == "user"
    with (
        patch(
            "aioptdevices.interface.Interface.get_data",
            return_value=mock_ptdevices_level,
        ),
        patch(
            "homeassistant.components.ptdevices.async_setup_entry",
            return_value=True,
        ),
    ):
        result1 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            {
                CONF_API_TOKEN: "test-api-token",
            },
        )
        await hass.async_block_till_done()

    assert result1["type"] is FlowResultType.CREATE_ENTRY
    assert result1["title"] == "User Name"
    assert result1["data"] == {
        "api_token": "test-api-token",
    }

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    with (
        patch(
            "aioptdevices.interface.Interface.get_data",
            return_value=mock_ptdevices_level,
        ),
        patch(
            "homeassistant.components.ptdevices.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_API_TOKEN: "test-api-token",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_flow_invalid_auth(hass: HomeAssistant) -> None:
    """Test A flow with an invalid API Token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "aioptdevices.interface.Interface.get_data",
            side_effect=PTDevicesUnauthorizedError,
        ),
        patch(
            "homeassistant.components.ptdevices.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_TOKEN: "test-api-tkn",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_flow_cannot_connect(
    hass: HomeAssistant,
) -> None:
    """Test A flow that returns a RequestError."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    with (
        patch(
            "aioptdevices.interface.Interface.get_data",
            side_effect=PTDevicesRequestError,
        ),
        patch(
            "homeassistant.components.ptdevices.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_TOKEN: "test-api-token",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_resp_forbidden_error(hass: HomeAssistant) -> None:
    """Test A flow that returns a ForbiddenError."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "aioptdevices.interface.Interface.get_data",
            side_effect=PTDevicesForbiddenError,
        ),
        patch(
            "homeassistant.components.ptdevices.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_TOKEN: "test-api-tkn",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
