"""Test the aidot config flow."""

from unittest.mock import patch

from aidot.const import CONF_LOGIN_INFO, SUPPORTED_COUNTRY_NAMES
from aidot.exceptions import AidotUserOrPassIncorrect
import pytest

from homeassistant import config_entries
from homeassistant.components.aidot.const import DOMAIN
from homeassistant.const import CONF_COUNTRY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_COUNTRY, TEST_EMAIL, TEST_PASSWORD

TEST_HOME = "Test Home"
TEST_LOGIN_RESPONSE = {
    "id": "314159263367458941151",
    "accessToken": "1234567891011121314151617181920",
    "refreshToken": "2021222324252627282930313233343",
    "expiresIn": 10000,
    "nickname": TEST_EMAIL,
    "username": TEST_EMAIL,
}


@pytest.fixture(name="aidot_login", autouse=True)
def aidot_login_fixture():
    """Aidot and entry setup."""
    with (
        patch(
            "homeassistant.components.aidot.config_flow.AidotClient.async_post_login",
            return_value=TEST_LOGIN_RESPONSE,
        ),
        patch("homeassistant.components.aidot.async_setup_entry", return_value=True),
        patch("homeassistant.components.aidot.async_unload_entry", return_value=True),
    ):
        yield


async def test_config_flow_user_init(hass: HomeAssistant) -> None:
    """Test a failed config flow user init."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


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

    assert result["data"] == {CONF_LOGIN_INFO: TEST_LOGIN_RESPONSE}


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


async def test_config_flow_login_user_password_incorrect(hass: HomeAssistant) -> None:
    """Test a failed config flow using cloud connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.aidot.config_flow.AidotClient.async_post_login",
        side_effect=AidotUserOrPassIncorrect(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_COUNTRY: TEST_COUNTRY,
                CONF_USERNAME: TEST_EMAIL,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )

    assert result["errors"] == {"base": "account_pwd_incorrect"}
