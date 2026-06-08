"""Tests for UniFi AP Direct config flow."""

from unifi_ap import UniFiAPConnectionException

from homeassistant.components.unifi_direct.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_CONFIG


async def test_user_flow_success(
    hass: HomeAssistant, mock_setup_entry, mock_unifiap
) -> None:
    """Test a successful config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "host": "192.168.1.2",
            "username": "admin",
            "password": "password",
            "port": 22,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "UniFi AP (192.168.1.2)"
    assert result["data"] == {
        "host": "192.168.1.2",
        "username": "admin",
        "password": "password",
        "port": 22,
    }


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_setup_entry, mock_unifiap
) -> None:
    """Test config flow when connection fails."""
    # Make the UniFiAP.get_clients raise an exception
    mock_unifiap.return_value.get_clients.side_effect = UniFiAPConnectionException(
        "fail"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    user_input = {
        "host": "192.168.1.2",
        "username": "admin",
        "password": "password",
        "port": 22,
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Remove the UniFiAP.get_clients side effect and see if the flow recovers
    mock_unifiap.return_value.get_clients.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_entry_exists(
    hass: HomeAssistant, mock_setup_entry, mock_unifiap, mock_config_entry
) -> None:
    """Test where an entry already exists and we try to set it up."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow(hass: HomeAssistant, mock_setup_entry, mock_unifiap) -> None:
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
    hass: HomeAssistant, mock_setup_entry, mock_unifiap
) -> None:
    """Test import config flow when connection fails."""
    mock_unifiap.return_value.get_clients.side_effect = UniFiAPConnectionException(
        "fail"
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
