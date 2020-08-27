"""Tests for the GogoGate2 component."""
from gogogate2_api import GogoGate2Api
from gogogate2_api.common import ApiError
from gogogate2_api.const import ApiErrorCode

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_FORM

from .common import ComponentFactory

from tests.async_mock import MagicMock, patch


async def test_auth_fail(
    hass: HomeAssistant, component_factory: ComponentFactory
) -> None:
    """Test authorization failures."""
    api_mock: GogoGate2Api = MagicMock(spec=GogoGate2Api)

    with patch(
        "homeassistant.components.gogogate2.async_setup", return_value=True
    ), patch(
        "homeassistant.components.gogogate2.async_setup_entry",
        return_value=True,
    ):
        await component_factory.configure_component()
        component_factory.api_class_mock.return_value = api_mock

        api_mock.reset_mock()
        api_mock.info.side_effect = ApiError(ApiErrorCode.CREDENTIALS_INCORRECT, "blah")
        result = await hass.config_entries.flow.async_init(
            "gogogate2", context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_IP_ADDRESS: "127.0.0.2",
                CONF_USERNAME: "user0",
                CONF_PASSWORD: "password0",
            },
        )
        assert result
        assert result["type"] == RESULT_TYPE_FORM
        assert result["errors"] == {
            "base": "invalid_auth",
        }

        api_mock.reset_mock()
        api_mock.info.side_effect = Exception("Generic connection error.")
        result = await hass.config_entries.flow.async_init(
            "gogogate2", context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_IP_ADDRESS: "127.0.0.2",
                CONF_USERNAME: "user0",
                CONF_PASSWORD: "password0",
            },
        )
        assert result
        assert result["type"] == RESULT_TYPE_FORM
        assert result["errors"] == {"base": "cannot_connect"}
