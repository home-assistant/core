"""Test the Hydrawise config flow."""

from unittest.mock import AsyncMock

from aiohttp import ClientError
from pydrawise import APIError, auth as pydrawise_auth
from pydrawise.exceptions import NotAuthorizedError
from pydrawise.schema import User
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.hydrawise.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.aiohttp_client import async_get_clientsession

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_auth: AsyncMock,
    mock_pydrawise: AsyncMock,
    user: User,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "asdf@asdf.com",
            CONF_PASSWORD: "__password__",
            CONF_API_KEY: "__api-key__",
        },
    )
    mock_pydrawise.get_user.return_value = user
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "asdf@asdf.com"
    assert result["data"] == {
        CONF_USERNAME: "asdf@asdf.com",
        CONF_PASSWORD: "__password__",
        CONF_API_KEY: "__api-key__",
    }
    assert result["result"].unique_id == f"hydrawise-{user.customer_id}"
    assert len(mock_setup_entry.mock_calls) == 1
    mock_auth.check.assert_awaited_once_with()
    pydrawise_auth.HybridAuth.assert_called_once_with(
        "asdf@asdf.com",
        "__password__",
        "__api-key__",
        session=async_get_clientsession(hass),
    )
    mock_pydrawise.get_user.assert_awaited_once_with(fetch_zones=False)


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (ClientError("XXX"), "cannot_connect"),
        (APIError("unavailable"), "cannot_connect"),
        (NotAuthorizedError("HTTP 401"), "invalid_auth"),
        (TimeoutError(), "timeout_connect"),
        (Exception("Boom"), "unknown"),
    ],
)
async def test_form_api_error(
    hass: HomeAssistant,
    mock_auth: AsyncMock,
    mock_pydrawise: AsyncMock,
    user: User,
    side_effect: Exception,
    error: str,
) -> None:
    """Test we handle API errors."""
    mock_pydrawise.get_user.side_effect = side_effect

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    data = {
        CONF_USERNAME: "asdf@asdf.com",
        CONF_PASSWORD: "__password__",
        CONF_API_KEY: "__api-key__",
    }
    result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"], data
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_pydrawise.get_user.reset_mock(side_effect=True)
    mock_pydrawise.get_user.return_value = user
    result = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (ClientError("XXX"), "cannot_connect"),
        (APIError("unavailable"), "cannot_connect"),
        (NotAuthorizedError("HTTP 401"), "invalid_auth"),
        (TimeoutError(), "timeout_connect"),
        (Exception("Boom"), "unknown"),
    ],
)
async def test_form_auth_check_error(
    hass: HomeAssistant,
    mock_auth: AsyncMock,
    mock_pydrawise: AsyncMock,
    user: User,
    side_effect: Exception,
    error: str,
) -> None:
    """Test we handle errors while checking the credentials."""
    mock_auth.check.side_effect = side_effect

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    data = {
        CONF_USERNAME: "asdf@asdf.com",
        CONF_PASSWORD: "__password__",
        CONF_API_KEY: "__api-key__",
    }
    result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"], data
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_auth.check.reset_mock(side_effect=True)
    mock_pydrawise.get_user.return_value = user
    result = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_auth")
async def test_form_already_configured(
    hass: HomeAssistant,
    mock_pydrawise: AsyncMock,
    user: User,
) -> None:
    """Test we abort when the account is already configured."""
    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "asdf@asdf.com",
            CONF_PASSWORD: "__password__",
            CONF_API_KEY: "__api-key__",
        },
        unique_id=f"hydrawise-{user.customer_id}",
    ).add_to_hass(hass)
    mock_pydrawise.get_user.return_value = user

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "asdf@asdf.com",
            CONF_PASSWORD: "__password__",
            CONF_API_KEY: "__api-key__",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(
    hass: HomeAssistant,
    user: User,
    mock_auth: AsyncMock,
    mock_pydrawise: AsyncMock,
) -> None:
    """Test that re-authorization works."""
    mock_config_entry = MockConfigEntry(
        title="Hydrawise",
        domain=DOMAIN,
        data={
            CONF_USERNAME: "asdf@asdf.com",
            CONF_PASSWORD: "bad-password",
            CONF_API_KEY: "__api-key__",
        },
        unique_id="hydrawise-12345",
    )
    mock_config_entry.add_to_hass(hass)

    mock_config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    [result] = flows
    assert result["step_id"] == "reauth_confirm"

    mock_pydrawise.get_user.return_value = user
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "__password__",
            CONF_API_KEY: "__api-key__",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_USERNAME: "asdf@asdf.com",
        CONF_PASSWORD: "__password__",
        CONF_API_KEY: "__api-key__",
    }


@pytest.mark.usefixtures("mock_auth")
async def test_reauth_wrong_account(
    hass: HomeAssistant,
    user: User,
    mock_pydrawise: AsyncMock,
) -> None:
    """Test that reauthenticating with a different account aborts."""
    mock_config_entry = MockConfigEntry(
        title="Hydrawise",
        domain=DOMAIN,
        data={
            CONF_USERNAME: "asdf@asdf.com",
            CONF_PASSWORD: "bad-password",
            CONF_API_KEY: "__api-key__",
        },
        unique_id="hydrawise-67890",
    )
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    mock_pydrawise.get_user.return_value = user
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "__password__",
            CONF_API_KEY: "__api-key__",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert mock_config_entry.data[CONF_PASSWORD] == "bad-password"


@pytest.mark.usefixtures("mock_auth")
async def test_reauth_legacy_entry(
    hass: HomeAssistant,
    user: User,
    mock_pydrawise: AsyncMock,
) -> None:
    """Test reauthenticating an entry from the legacy API, which has no username."""
    mock_config_entry = MockConfigEntry(
        title="Hydrawise",
        domain=DOMAIN,
        data={CONF_API_KEY: "abc123"},
        unique_id=f"hydrawise-{user.customer_id}",
        version=1,
    )
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    assert CONF_USERNAME in result["data_schema"].schema

    mock_pydrawise.get_user.return_value = user
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "asdf@asdf.com",
            CONF_PASSWORD: "__password__",
            CONF_API_KEY: "__api-key__",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_USERNAME: "asdf@asdf.com",
        CONF_PASSWORD: "__password__",
        CONF_API_KEY: "__api-key__",
    }


async def test_reauth_fails(
    hass: HomeAssistant, mock_auth: AsyncMock, mock_pydrawise: AsyncMock, user: User
) -> None:
    """Test that the reauth flow handles API errors."""
    mock_config_entry = MockConfigEntry(
        title="Hydrawise",
        domain=DOMAIN,
        data={
            CONF_USERNAME: "asdf@asdf.com",
            CONF_PASSWORD: "bad-password",
            CONF_API_KEY: "__api-key__",
        },
        unique_id="hydrawise-12345",
    )
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    mock_auth.check.side_effect = NotAuthorizedError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "__password__",
            CONF_API_KEY: "__api-key__",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    mock_auth.check.reset_mock(side_effect=True)
    mock_pydrawise.get_user.return_value = user
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "__password__",
            CONF_API_KEY: "__api-key__",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.usefixtures("mock_auth")
async def test_reconfigure(
    hass: HomeAssistant,
    user: User,
    mock_pydrawise: AsyncMock,
) -> None:
    """Test reconfiguring the account credentials."""
    mock_config_entry = MockConfigEntry(
        title="asdf@asdf.com",
        domain=DOMAIN,
        data={
            CONF_USERNAME: "asdf@asdf.com",
            CONF_PASSWORD: "__password__",
            CONF_API_KEY: "__api-key__",
        },
        unique_id=f"hydrawise-{user.customer_id}",
    )
    mock_config_entry.add_to_hass(hass)
    mock_pydrawise.get_user.return_value = user

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "new@asdf.com",
            CONF_PASSWORD: "__new-password__",
            CONF_API_KEY: "__new-api-key__",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.title == "new@asdf.com"
    assert mock_config_entry.data == {
        CONF_USERNAME: "new@asdf.com",
        CONF_PASSWORD: "__new-password__",
        CONF_API_KEY: "__new-api-key__",
    }


@pytest.mark.usefixtures("mock_auth")
async def test_reconfigure_wrong_account(
    hass: HomeAssistant,
    user: User,
    mock_pydrawise: AsyncMock,
) -> None:
    """Test that reconfiguring with a different account aborts."""
    mock_config_entry = MockConfigEntry(
        title="asdf@asdf.com",
        domain=DOMAIN,
        data={
            CONF_USERNAME: "asdf@asdf.com",
            CONF_PASSWORD: "__password__",
            CONF_API_KEY: "__api-key__",
        },
        unique_id="hydrawise-67890",
    )
    mock_config_entry.add_to_hass(hass)
    mock_pydrawise.get_user.return_value = user

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "other@asdf.com",
            CONF_PASSWORD: "__password__",
            CONF_API_KEY: "__api-key__",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert mock_config_entry.data[CONF_USERNAME] == "asdf@asdf.com"


async def test_reconfigure_error(
    hass: HomeAssistant,
    user: User,
    mock_auth: AsyncMock,
    mock_pydrawise: AsyncMock,
) -> None:
    """Test that the reconfigure flow recovers from an error."""
    mock_config_entry = MockConfigEntry(
        title="asdf@asdf.com",
        domain=DOMAIN,
        data={
            CONF_USERNAME: "asdf@asdf.com",
            CONF_PASSWORD: "__password__",
            CONF_API_KEY: "__api-key__",
        },
        unique_id=f"hydrawise-{user.customer_id}",
    )
    mock_config_entry.add_to_hass(hass)
    mock_pydrawise.get_user.return_value = user
    mock_auth.check.side_effect = NotAuthorizedError("HTTP 401")
    data = {
        CONF_USERNAME: "asdf@asdf.com",
        CONF_PASSWORD: "__new-password__",
        CONF_API_KEY: "__api-key__",
    }

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], data)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    mock_auth.check.reset_mock(side_effect=True)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], data)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "__new-password__"


@pytest.mark.usefixtures("mock_auth")
async def test_reconfigure_legacy_entry(
    hass: HomeAssistant,
    user: User,
    mock_pydrawise: AsyncMock,
) -> None:
    """Test reconfiguring an entry from the legacy API, which has no username."""
    mock_config_entry = MockConfigEntry(
        title="Hydrawise",
        domain=DOMAIN,
        data={CONF_API_KEY: "abc123"},
        unique_id=f"hydrawise-{user.customer_id}",
        version=1,
    )
    mock_config_entry.add_to_hass(hass)
    mock_pydrawise.get_user.return_value = user

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "asdf@asdf.com",
            CONF_PASSWORD: "__password__",
            CONF_API_KEY: "__api-key__",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        CONF_USERNAME: "asdf@asdf.com",
        CONF_PASSWORD: "__password__",
        CONF_API_KEY: "__api-key__",
    }
