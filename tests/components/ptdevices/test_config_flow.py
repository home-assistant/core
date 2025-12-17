"""Test the PTDevices config flow."""

from unittest.mock import AsyncMock, patch

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

from tests.common import MockConfigEntry


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


async def test_flow_missing_title(
    hass: HomeAssistant,
    mock_ptdevices_level_missing_title: PTDevicesResponse,
) -> None:
    """Test A flow that returns an malformed response."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    with (
        patch(
            "aioptdevices.interface.Interface.get_data",
            return_value=mock_ptdevices_level_missing_title,
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
    assert result["errors"] == {"base": "malformed_response"}


async def test_flow_reauth_success(
    hass: HomeAssistant,
    mock_ptdevices_setup_entry: AsyncMock,
    mock_ptdevices_config_entry: MockConfigEntry,
) -> None:
    """Test A flow that successfully reauthorizes a device."""
    # New configuration data with a different API token
    new_conf_data = {
        CONF_API_TOKEN: "test-api-token-new",
    }

    mock_ptdevices_config_entry.add_to_hass(hass)

    # Start and confirm the reauth flow
    result = await mock_ptdevices_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]
    assert result["step_id"] == "reauth_confirm"

    # Make sure the context is correct
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert flows[0]["context"]["title_placeholders"] == {"name": "Home"}

    # Try to reauthorize the device
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=new_conf_data
    )
    await hass.async_block_till_done()

    # Make sure the reauth ran as we expected
    mock_ptdevices_setup_entry.assert_called_once()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    # Check that the entry was updated with the new configuration
    assert mock_ptdevices_config_entry.data[CONF_API_TOKEN] == "test-api-token-new"


async def test_flow_reauth_invalid_auth(
    hass: HomeAssistant,
    mock_ptdevices_config_entry: MockConfigEntry,
) -> None:
    """Test A flow that runs a reauth with an unauthorized and forbidden."""
    # New configuration data with a different API token
    new_conf_data = {
        CONF_API_TOKEN: "test-api-token-new",
    }

    mock_ptdevices_config_entry.add_to_hass(hass)

    # Start and confirm the reauth flow
    result = await mock_ptdevices_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]
    assert result["step_id"] == "reauth_confirm"

    # Make sure the context is correct
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert flows[0]["context"]["title_placeholders"] == {"name": "Home"}

    # Try reauthorizing the device but getting an unauthorized error
    with patch(
        "aioptdevices.interface.Interface.get_data",
        side_effect=PTDevicesUnauthorizedError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=new_conf_data
        )
        await hass.async_block_till_done()

    # Make sure the reauth ran as we expected
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert result["step_id"] == "reauth_confirm"

    # Try reauthorizing the device but getting an forbidden error
    with patch(
        "aioptdevices.interface.Interface.get_data",
        side_effect=PTDevicesForbiddenError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=new_conf_data
        )
        await hass.async_block_till_done()

    # Make sure the reauth ran as we expected
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert result["step_id"] == "reauth_confirm"

    # Check that the entry was updated with the new configuration
    assert mock_ptdevices_config_entry.data[CONF_API_TOKEN] == "test-api-token"


async def test_flow_reauth_cannot_connect(
    hass: HomeAssistant,
    mock_ptdevices_config_entry: MockConfigEntry,
) -> None:
    """Test A flow that runs a reauth with a request error response."""
    # New configuration data with a different API token
    new_conf_data = {
        CONF_API_TOKEN: "test-api-token-new",
    }

    mock_ptdevices_config_entry.add_to_hass(hass)

    # Start and confirm the reauth flow
    result = await mock_ptdevices_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]
    assert result["step_id"] == "reauth_confirm"

    # Make sure the context is correct
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert flows[0]["context"]["title_placeholders"] == {"name": "Home"}

    # Try reauthorizing the device but getting a request error
    with patch(
        "aioptdevices.interface.Interface.get_data",
        side_effect=PTDevicesRequestError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=new_conf_data
        )
        await hass.async_block_till_done()

    # Make sure the reauth ran as we expected
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert result["step_id"] == "reauth_confirm"

    # Check that the entry was updated with the new configuration
    assert mock_ptdevices_config_entry.data[CONF_API_TOKEN] == "test-api-token"


async def test_flow_reauth_malformed_response(
    hass: HomeAssistant,
    mock_ptdevices_config_entry: MockConfigEntry,
    mock_ptdevices_level_missing_title: PTDevicesResponse,
) -> None:
    """Test A flow that runs a reauth with a request error response."""
    # New configuration data with a different API token
    new_conf_data = {
        CONF_API_TOKEN: "test-api-token-new",
    }

    mock_ptdevices_config_entry.add_to_hass(hass)

    # Start and confirm the reauth flow
    result = await mock_ptdevices_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]
    assert result["step_id"] == "reauth_confirm"

    # Make sure the context is correct
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert flows[0]["context"]["title_placeholders"] == {"name": "Home"}

    # Try reauthorizing the device but getting an unauthorized error
    with (
        patch(
            "aioptdevices.interface.Interface.get_data",
            return_value=mock_ptdevices_level_missing_title,
        ),
        patch(
            "homeassistant.components.ptdevices.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=new_conf_data
        )
        await hass.async_block_till_done()

    # Make sure the reauth ran as we expected
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "malformed_response"}
    assert result["step_id"] == "reauth_confirm"

    # Check that the entry was updated with the new configuration
    assert mock_ptdevices_config_entry.data[CONF_API_TOKEN] == "test-api-token"
