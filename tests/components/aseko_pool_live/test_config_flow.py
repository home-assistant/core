"""Test the Aseko Pool Live config flow."""
from unittest.mock import AsyncMock, patch

from aioaseko import AccountInfo, APIUnavailable, InvalidAuthCredentials
import pytest

from homeassistant import config_entries, setup
from homeassistant.components.aseko_pool_live.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.aseko_pool_live.config_flow.WebAccount.login",
        return_value=AccountInfo("aseko@example.com", "a_user_id", "any_language"),
    ), patch(
        "homeassistant.components.aseko_pool_live.config_flow.MobileAccount",
    ) as mock_mobile_account, patch(
        "homeassistant.components.aseko_pool_live.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        mobile_account = mock_mobile_account.return_value
        mobile_account.login = AsyncMock()
        mobile_account.access_token = "any_access_token"
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "aseko@example.com",
                CONF_PASSWORD: "passw0rd",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "aseko@example.com"
    assert result2["data"] == {CONF_ACCESS_TOKEN: "any_access_token"}
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("error_web", "error_mobile", "reason"),
    [
        (APIUnavailable, None, "cannot_connect"),
        (InvalidAuthCredentials, None, "invalid_auth"),
        (Exception, None, "unknown"),
        (None, APIUnavailable, "cannot_connect"),
        (None, InvalidAuthCredentials, "invalid_auth"),
        (None, Exception, "unknown"),
    ],
)
async def test_get_account_info_exceptions(
    hass: HomeAssistant, error_web: Exception, error_mobile: Exception, reason: str
) -> None:
    """Test we handle config flow exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.aseko_pool_live.config_flow.WebAccount.login",
        return_value=AccountInfo("aseko@example.com", "a_user_id", "any_language"),
        side_effect=error_web,
    ), patch(
        "homeassistant.components.aseko_pool_live.config_flow.MobileAccount.login",
        side_effect=error_mobile,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "aseko@example.com",
                CONF_PASSWORD: "passw0rd",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": reason}
