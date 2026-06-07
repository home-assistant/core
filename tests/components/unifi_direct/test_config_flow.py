"""Tests for UniFi AP Direct config flow."""

from unifi_ap import UniFiAPConnectionException

from homeassistant.components.unifi_direct.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_user_flow_success(
    hass: HomeAssistant, mock_unifiap, mock_unifiap_config_flow
) -> None:
    """Test a successful config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "host": "192.168.1.2",
            "username": "admin",
            "password": "password",
            "port": 22,
        },
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_unifiap, mock_unifiap_config_flow
) -> None:
    """Test config flow when connection fails."""
    # Make the UniFiAP.get_clients raise an exception
    mock_unifiap_config_flow.return_value.get_clients.side_effect = (
        UniFiAPConnectionException("fail")
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "host": "192.168.1.2",
            "username": "admin",
            "password": "password",
            "port": 22,
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_import_flow(
    hass: HomeAssistant, mock_unifiap, mock_unifiap_config_flow
) -> None:
    """Test import initiated flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: "192.168.1.2",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
            CONF_PORT: 22,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "UniFi AP (192.168.1.2)"
    assert result["data"] == {
        CONF_HOST: "192.168.1.2",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "password",
        CONF_PORT: 22,
    }


async def test_import_flow_cannot_connect(
    hass: HomeAssistant, mock_unifiap, mock_unifiap_config_flow
) -> None:
    """Test import config flow when connection fails."""
    mock_unifiap_config_flow.return_value.get_clients.side_effect = (
        UniFiAPConnectionException("fail")
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: "192.168.1.2",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
            CONF_PORT: 22,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
