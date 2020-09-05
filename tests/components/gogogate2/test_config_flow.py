"""Tests for the GogoGate2 component."""
from gogogate2_api import GogoGate2Api
from gogogate2_api.common import ApiError
from gogogate2_api.const import GogoGate2ApiErrorCode

from homeassistant.components.gogogate2.const import DEVICE_TYPE_GOGOGATE2
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_DEVICE,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_FORM

from tests.async_mock import MagicMock, patch


@patch("homeassistant.components.gogogate2.async_setup", return_value=True)
@patch("homeassistant.components.gogogate2.async_setup_entry", return_value=True)
@patch("homeassistant.components.gogogate2.common.GogoGate2Api")
async def test_auth_fail(
    gogogate2api_mock, async_setup_entry_mock, async_setup_mock, hass: HomeAssistant
) -> None:
    """Test authorization failures."""
    api: GogoGate2Api = MagicMock(spec=GogoGate2Api)
    gogogate2api_mock.return_value = api

    api.reset_mock()
    api.info.side_effect = ApiError(GogoGate2ApiErrorCode.CREDENTIALS_INCORRECT, "blah")
    result = await hass.config_entries.flow.async_init(
        "gogogate2", context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICE: DEVICE_TYPE_GOGOGATE2,
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

    api.reset_mock()
    api.info.side_effect = Exception("Generic connection error.")
    result = await hass.config_entries.flow.async_init(
        "gogogate2", context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICE: DEVICE_TYPE_GOGOGATE2,
            CONF_IP_ADDRESS: "127.0.0.2",
            CONF_USERNAME: "user0",
            CONF_PASSWORD: "password0",
        },
    )
    assert result
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_connect"}
