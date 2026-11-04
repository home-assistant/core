"""Tests for the Lutron GRAFIK Eye config flow."""

from unittest.mock import MagicMock

from grafikeye.exceptions import (
    GrafikEyeAuthenticationError,
    GrafikEyeConnectionError,
    GrafikEyeConnectionInUseError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.lutron_grafik_eye.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

USER_INPUT = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: 2323,
    CONF_PASSWORD: "some_password",
}


async def test_user_form(hass: HomeAssistant) -> None:
    """Test the initial configuration form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_user_success(
    hass: HomeAssistant,
    mock_controller: MagicMock,
) -> None:
    """Test successful configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "GRAFIK Eye (192.168.1.100)"
    assert result["data"] == USER_INPUT
    mock_controller.assert_called_once_with(
        host=USER_INPUT[CONF_HOST],
        port=USER_INPUT[CONF_PORT],
        login=USER_INPUT[CONF_PASSWORD],
    )
    mock_controller.return_value.connect.assert_awaited_once()
    mock_controller.return_value.disconnect.assert_awaited_once()


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (GrafikEyeAuthenticationError, "invalid_auth"),
        (GrafikEyeConnectionInUseError, "connection_in_use"),
        (GrafikEyeConnectionError, "cannot_connect"),
    ],
)
async def test_user_connection_error(
    hass: HomeAssistant,
    mock_controller: MagicMock,
    exception: type[Exception],
    error: str,
) -> None:
    """Test connection errors."""
    mock_controller.return_value.connect.side_effect = exception()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert result["data_schema"]({CONF_PASSWORD: "test"}) == {
        **USER_INPUT,
        CONF_PASSWORD: "test",
    }
    mock_controller.return_value.disconnect.assert_awaited_once()

    # Retry after the connection error has been resolved.
    mock_controller.return_value.connect.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == USER_INPUT
    assert mock_controller.return_value.connect.await_count == 2
    assert mock_controller.return_value.disconnect.await_count == 2


async def test_user_duplicate(
    hass: HomeAssistant,
    mock_controller: MagicMock,
) -> None:
    """Test duplicate configuration is rejected."""
    MockConfigEntry(domain=DOMAIN, data=USER_INPUT).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_controller.assert_not_called()


async def test_user_different_port(
    hass: HomeAssistant,
    mock_controller: MagicMock,
) -> None:
    """Test the same host with a different port is allowed."""
    MockConfigEntry(domain=DOMAIN, data=USER_INPUT).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    user_input = {**USER_INPUT, CONF_PORT: 10000}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == user_input
    mock_controller.return_value.connect.assert_awaited_once()
