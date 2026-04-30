"""Test the CatGenie config flow."""

from unittest.mock import AsyncMock, MagicMock

from catgenie.exceptions import CatGenieAuthenticationError, CatGenieException

from homeassistant import config_entries
from homeassistant.components.catgenie.config_flow import CONF_COUNTRY_CODE, CONF_PHONE
from homeassistant.components.catgenie.const import DOMAIN
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_catgenie_auth: MagicMock,
) -> None:
    """Test the full config flow: phone -> SMS code -> entry created."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_COUNTRY_CODE: 61, CONF_PHONE: "499999999"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "code"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"code": "123456"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "CatGenie (499999999)"
    assert result["data"] == {CONF_TOKEN: "test-refresh-token"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_phone_step_cannot_connect(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_catgenie_auth: MagicMock,
) -> None:
    """Test we handle error when requesting login code fails."""
    mock_catgenie_auth.request_login_code.side_effect = CatGenieAuthenticationError(
        "Connection error"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_COUNTRY_CODE: 61, CONF_PHONE: "499999999"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Recover
    mock_catgenie_auth.request_login_code.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_COUNTRY_CODE: 61, CONF_PHONE: "499999999"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "code"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"code": "123456"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_phone_step_unknown_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_catgenie_auth: MagicMock,
) -> None:
    """Test we handle unexpected exception on phone step."""
    mock_catgenie_auth.request_login_code.side_effect = CatGenieException(
        "Unexpected API error"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_COUNTRY_CODE: 61, CONF_PHONE: "499999999"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    # Recover
    mock_catgenie_auth.request_login_code.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_COUNTRY_CODE: 61, CONF_PHONE: "499999999"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "code"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"code": "123456"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_code_step_invalid_auth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_catgenie_auth: MagicMock,
) -> None:
    """Test we handle invalid auth on code step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_COUNTRY_CODE: 61, CONF_PHONE: "499999999"},
    )
    assert result["step_id"] == "code"

    mock_catgenie_auth.login.side_effect = CatGenieAuthenticationError("Invalid code")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"code": "wrong"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Recover
    mock_catgenie_auth.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"code": "123456"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_code_step_unknown_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_catgenie_auth: MagicMock,
) -> None:
    """Test we handle unexpected exception on code step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_COUNTRY_CODE: 61, CONF_PHONE: "499999999"},
    )

    mock_catgenie_auth.login.side_effect = CatGenieException("Unexpected API error")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"code": "123456"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    # Recover
    mock_catgenie_auth.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"code": "123456"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_catgenie_auth: MagicMock,
) -> None:
    """Test we abort if already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_COUNTRY_CODE: 61, CONF_PHONE: "499999999"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"code": "123456"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_catgenie_auth: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the re-authentication flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_COUNTRY_CODE: 61, CONF_PHONE: "499999999"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_code"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"code": "654321"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_confirm_cannot_connect(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_catgenie_auth: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test re-auth when requesting code fails."""
    mock_config_entry.add_to_hass(hass)
    mock_catgenie_auth.request_login_code.side_effect = CatGenieAuthenticationError(
        "fail"
    )

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_COUNTRY_CODE: 61, CONF_PHONE: "499999999"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Recover
    mock_catgenie_auth.request_login_code.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_COUNTRY_CODE: 61, CONF_PHONE: "499999999"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_code"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"code": "654321"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_code_invalid_auth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_catgenie_auth: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test re-auth when SMS code is invalid."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_COUNTRY_CODE: 61, CONF_PHONE: "499999999"},
    )
    assert result["step_id"] == "reauth_code"

    mock_catgenie_auth.login.side_effect = CatGenieAuthenticationError("bad code")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"code": "wrong"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Recover
    mock_catgenie_auth.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"code": "654321"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_confirm_unknown_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_catgenie_auth: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test re-auth when requesting code raises unexpected exception."""
    mock_config_entry.add_to_hass(hass)
    mock_catgenie_auth.request_login_code.side_effect = CatGenieException(
        "Unexpected API error"
    )

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_COUNTRY_CODE: 61, CONF_PHONE: "499999999"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    # Recover
    mock_catgenie_auth.request_login_code.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_COUNTRY_CODE: 61, CONF_PHONE: "499999999"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_code"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"code": "654321"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_code_unknown_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_catgenie_auth: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test re-auth when SMS code step raises unexpected exception."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_COUNTRY_CODE: 61, CONF_PHONE: "499999999"},
    )
    assert result["step_id"] == "reauth_code"

    mock_catgenie_auth.login.side_effect = CatGenieException("Unexpected API error")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"code": "123456"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    # Recover
    mock_catgenie_auth.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"code": "654321"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
