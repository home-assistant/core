"""Tests for UniFi Direct config flow."""

from unifi_ap import UniFiAPConnectionException

from homeassistant import data_entry_flow
from homeassistant.components.unifi_direct.const import DOMAIN
from homeassistant.core import HomeAssistant


async def test_user_flow_success(hass: HomeAssistant, mock_unifiap_validate) -> None:
    """Test a successful config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "host": "192.168.1.2",
            "username": "admin",
            "password": "password",
            "port": 22,
        },
    )

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_unifiap_validate
) -> None:
    """Test config flow when connection fails."""
    # Make the UniFiAP.get_clients raise an exception
    mock_unifiap_validate.return_value.get_clients.side_effect = (
        UniFiAPConnectionException("fail")
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "host": "192.168.1.2",
            "username": "admin",
            "password": "password",
            "port": 22,
        },
    )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
