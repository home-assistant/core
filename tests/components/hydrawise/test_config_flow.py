"""Test the Hydrawise config flow."""

from unittest.mock import AsyncMock

from aiohttp import ClientError
from pydrawise.exceptions import NotAuthorizedError
from pydrawise.schema import User
import pytest

from homeassistant import config_entries
from homeassistant.components.hydrawise.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

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
    assert len(mock_setup_entry.mock_calls) == 1
    mock_auth.check.assert_awaited_once_with()
    mock_pydrawise.get_user.assert_awaited_once_with(fetch_zones=False)


async def test_form_api_error(
    hass: HomeAssistant, mock_auth: AsyncMock, mock_pydrawise: AsyncMock, user: User
) -> None:
    """Test we handle API errors."""
    mock_pydrawise.get_user.side_effect = ClientError("XXX")

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
    assert result["errors"] == {"base": "cannot_connect"}

    mock_pydrawise.get_user.reset_mock(side_effect=True)
    mock_pydrawise.get_user.return_value = user
    result = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_auth_connect_timeout(
    hass: HomeAssistant, mock_auth: AsyncMock, mock_pydrawise: AsyncMock
) -> None:
    """Test we handle connection timeout errors."""
    mock_auth.check.side_effect = TimeoutError
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_USER,
        },
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
    assert result["errors"] == {"base": "timeout_connect"}

    mock_auth.check.reset_mock(side_effect=True)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_client_connect_timeout(
    hass: HomeAssistant, mock_auth: AsyncMock, mock_pydrawise: AsyncMock, user: User
) -> None:
    """Test we handle API errors."""
    mock_pydrawise.get_user.side_effect = TimeoutError
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
    assert result["errors"] == {"base": "timeout_connect"}

    mock_pydrawise.get_user.reset_mock(side_effect=True)
    mock_pydrawise.get_user.return_value = user
    result = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_not_authorized_error(
    hass: HomeAssistant, mock_auth: AsyncMock, mock_pydrawise: AsyncMock
) -> None:
    """Test we handle API errors."""
    mock_auth.check.side_effect = NotAuthorizedError

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
    assert result["errors"] == {"base": "invalid_auth"}

    mock_auth.check.reset_mock(side_effect=True)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    assert result["type"] is FlowResultType.CREATE_ENTRY


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
