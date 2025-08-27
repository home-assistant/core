"""Tests for the TotalConnect config flow."""

from unittest.mock import AsyncMock, patch

from total_connect_client.exceptions import AuthenticationError

from homeassistant.components.totalconnect.const import (
    AUTO_BYPASS,
    CODE_REQUIRED,
    CONF_USERCODES,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_LOCATION, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration
from .const import LOCATION_ID, PASSWORD, USERNAME

from tests.common import MockConfigEntry


async def test_full_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_client: AsyncMock
) -> None:
    """Test user step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "locations"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERCODES: "7890"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_PASSWORD: PASSWORD,
        CONF_USERNAME: USERNAME,
        CONF_USERCODES: {LOCATION_ID: "7890"},
    }
    assert result["title"] == "Total Connect"
    assert result["options"] == {}
    assert result["result"].unique_id == USERNAME


async def test_login_errors(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_client: AsyncMock
) -> None:
    """Test login errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.totalconnect.config_flow.TotalConnectClient",
    ) as client:
        client.side_effect = AuthenticationError()

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "locations"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERCODES: "7890"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_usercode_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_client: AsyncMock,
    mock_location: AsyncMock,
) -> None:
    """Test user step with usercode errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "locations"

    mock_location.set_usercode.return_value = False

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERCODES: "7890"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "locations"
    assert result["errors"] == {CONF_LOCATION: "usercode"}

    mock_location.set_usercode.return_value = True

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERCODES: "7890"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_no_locations(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_client: AsyncMock,
    mock_location: AsyncMock,
) -> None:
    """Test no locations found."""

    mock_client.get_number_locations.return_value = 0
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_locations"


async def test_abort_if_already_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test abort if the account is already setup."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test login errors."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "abc"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert mock_config_entry.data[CONF_PASSWORD] == "abc"


async def test_reauth_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test login errors."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.totalconnect.config_flow.TotalConnectClient",
    ) as client:
        client.side_effect = AuthenticationError()

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: PASSWORD}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "invalid_auth"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: PASSWORD}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_options_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config flow options."""
    await setup_integration(hass, mock_config_entry)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={AUTO_BYPASS: True, CODE_REQUIRED: False}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {AUTO_BYPASS: True, CODE_REQUIRED: False}
