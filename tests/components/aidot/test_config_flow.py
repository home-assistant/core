"""Test the aidot config flow."""

from unittest.mock import AsyncMock

from aidot.const import CONF_LOGIN_INFO, SUPPORTED_COUNTRY_NAMES
from aidot.exceptions import AidotUserOrPassIncorrect

from homeassistant import config_entries
from homeassistant.components.aidot.const import DOMAIN
from homeassistant.const import CONF_COUNTRY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_COUNTRY, TEST_EMAIL, TEST_LOGIN_RESP, TEST_PASSWORD


async def test_config_flow_cloud_login_success(hass: HomeAssistant) -> None:
    """Test a failed config flow using cloud login success."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_COUNTRY: TEST_COUNTRY,
            CONF_USERNAME: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["data"] == {CONF_LOGIN_INFO: TEST_LOGIN_RESP}


async def test_async_show_country_form(hass: HomeAssistant) -> None:
    """Test that async_show_form is called with correct parameters in user step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert (
        result["data_schema"].schema[CONF_COUNTRY].container == SUPPORTED_COUNTRY_NAMES
    )


async def test_config_flow_login_user_password_incorrect(
    hass: HomeAssistant, mocked_aidot_client
) -> None:
    """Test a failed config flow using cloud connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    mocked_aidot_client.async_post_login = AsyncMock(
        side_effect=AidotUserOrPassIncorrect()
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_COUNTRY: TEST_COUNTRY,
            CONF_USERNAME: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["errors"] == {"base": "account_pwd_incorrect"}
