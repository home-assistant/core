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

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "asdf@asdf.com", CONF_PASSWORD: "__password__"},
    )
    mock_pydrawise.get_user.return_value = user
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Hydrawise"
    assert result2["data"] == {
        CONF_USERNAME: "asdf@asdf.com",
        CONF_PASSWORD: "__password__",
    }
    assert len(mock_setup_entry.mock_calls) == 1
    mock_pydrawise.get_user.assert_called_once_with()


async def test_form_api_error(
    hass: HomeAssistant, mock_pydrawise: AsyncMock, user: User
) -> None:
    """Test we handle API errors."""
    mock_pydrawise.get_user.side_effect = ClientError("XXX")

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    data = {CONF_USERNAME: "asdf@asdf.com", CONF_PASSWORD: "__password__"}
    result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"], data
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_pydrawise.get_user.reset_mock(side_effect=True)
    mock_pydrawise.get_user.return_value = user
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    assert result2["type"] is FlowResultType.CREATE_ENTRY


async def test_form_connect_timeout(
    hass: HomeAssistant, mock_pydrawise: AsyncMock, user: User
) -> None:
    """Test we handle API errors."""
    mock_pydrawise.get_user.side_effect = TimeoutError
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    data = {CONF_USERNAME: "asdf@asdf.com", CONF_PASSWORD: "__password__"}
    result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"], data
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "timeout_connect"}

    mock_pydrawise.get_user.reset_mock(side_effect=True)
    mock_pydrawise.get_user.return_value = user
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    assert result2["type"] is FlowResultType.CREATE_ENTRY


async def test_form_not_authorized_error(
    hass: HomeAssistant, mock_pydrawise: AsyncMock, user: User
) -> None:
    """Test we handle API errors."""
    mock_pydrawise.get_user.side_effect = NotAuthorizedError

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    data = {CONF_USERNAME: "asdf@asdf.com", CONF_PASSWORD: "__password__"}
    result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"], data
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    mock_pydrawise.get_user.reset_mock(side_effect=True)
    mock_pydrawise.get_user.return_value = user
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    assert result2["type"] is FlowResultType.CREATE_ENTRY


async def test_reauth(
    hass: HomeAssistant,
    user: User,
    mock_pydrawise: AsyncMock,
) -> None:
    """Test that re-authorization works."""
    mock_config_entry = MockConfigEntry(
        title="Hydrawise",
        domain=DOMAIN,
        data={
            CONF_API_KEY: "__api_key__",
        },
        unique_id="hydrawise-12345",
    )
    mock_config_entry.add_to_hass(hass)

    mock_config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    [result] = flows
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "asdf@asdf.com", CONF_PASSWORD: "__password__"},
    )
    mock_pydrawise.get_user.return_value = user
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
