"""Tests for Comelit SimpleHome config flow."""
from unittest.mock import patch

from aiocomelit.exceptions import CannotConnect

from homeassistant.components.comelit.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import MOCK_USER_DATA


async def test_user(hass: HomeAssistant) -> None:
    """Test starting a flow by user."""
    with patch(
        "aiocomelit.api.ComeliteSerialBridgeAPi.login",
    ), patch(
        "aiocomelit.api.ComeliteSerialBridgeAPi.logout",
    ), patch(
        "homeassistant.components.comelit.async_setup_entry"
    ) as mock_setup_entry, patch(
        "requests.get"
    ) as mock_request_get:
        mock_request_get.return_value.status_code = 200

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_HOST] == "fake_host"
        assert result["data"][CONF_PIN] == "1234"
        assert not result["result"].unique_id
        await hass.async_block_till_done()

    assert mock_setup_entry.called


async def test_exception_connection(hass: HomeAssistant) -> None:
    """Test starting a flow by user with a connection error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "aiocomelit.api.ComeliteSerialBridgeAPi.login",
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "cannot_connect"
