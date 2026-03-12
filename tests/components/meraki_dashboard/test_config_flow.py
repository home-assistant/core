"""Test the Meraki Dashboard config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.meraki_dashboard.api import MerakiDashboardApiAuthError
from homeassistant.components.meraki_dashboard.const import (
    CONF_INCLUDED_CLIENTS,
    CONF_NETWORK_ID,
    CONF_NETWORK_NAME,
    CONF_ORGANIZATION_ID,
    CONF_TRACK_BLUETOOTH_CLIENTS,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_INFRASTRUCTURE_DEVICES,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_flow(hass, mock_setup_entry: None) -> None:
    """Test the complete config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.meraki_dashboard.config_flow.MerakiDashboardApi.async_get_organizations",
            AsyncMock(return_value=[{"id": "1234", "name": "Home Org"}]),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.config_flow.MerakiDashboardApi.async_get_networks",
            AsyncMock(return_value=[{"id": "L_1111", "name": "HQ"}]),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_KEY: "api-key"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "network"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NETWORK_ID: "L_1111",
            CONF_TRACK_CLIENTS: True,
            CONF_TRACK_BLUETOOTH_CLIENTS: False,
            CONF_TRACK_INFRASTRUCTURE_DEVICES: True,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "HQ"
    assert result["data"] == {
        CONF_API_KEY: "api-key",
        CONF_ORGANIZATION_ID: "1234",
        CONF_NETWORK_ID: "L_1111",
        CONF_NETWORK_NAME: "HQ",
    }
    assert result["options"] == {
        CONF_TRACK_CLIENTS: True,
        CONF_TRACK_BLUETOOTH_CLIENTS: False,
        CONF_TRACK_INFRASTRUCTURE_DEVICES: True,
        CONF_INCLUDED_CLIENTS: [],
    }


async def test_flow_invalid_auth(hass, mock_setup_entry: None) -> None:
    """Test config flow with invalid authentication."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    with patch(
        "homeassistant.components.meraki_dashboard.config_flow.MerakiDashboardApi.async_get_organizations",
        AsyncMock(side_effect=MerakiDashboardApiAuthError("Invalid API key")),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_API_KEY: "invalid"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_flow_duplicate_network(
    hass, mock_setup_entry: None, mock_config_entry: MockConfigEntry
) -> None:
    """Test duplicate network handling."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    with (
        patch(
            "homeassistant.components.meraki_dashboard.config_flow.MerakiDashboardApi.async_get_organizations",
            AsyncMock(return_value=[{"id": "1234", "name": "Home Org"}]),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.config_flow.MerakiDashboardApi.async_get_networks",
            AsyncMock(return_value=[{"id": "L_1111", "name": "HQ"}]),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_KEY: "api-key"},
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NETWORK_ID: "L_1111",
            CONF_TRACK_CLIENTS: True,
            CONF_TRACK_BLUETOOTH_CLIENTS: False,
            CONF_TRACK_INFRASTRUCTURE_DEVICES: True,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(
    hass, mock_setup_entry: None, mock_config_entry: MockConfigEntry
) -> None:
    """Test options flow for selecting integration targets."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.meraki_dashboard.config_flow.MerakiDashboardApi.async_get_network_clients",
        AsyncMock(
            return_value=[
                {
                    "mac": "22:33:44:55:66:77",
                    "description": "Miles phone",
                }
            ]
        ),
    ):
        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_TRACK_CLIENTS: False,
                CONF_TRACK_BLUETOOTH_CLIENTS: False,
                CONF_TRACK_INFRASTRUCTURE_DEVICES: False,
                CONF_INCLUDED_CLIENTS: [],
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "at_least_one_enabled"}

    with patch(
        "homeassistant.components.meraki_dashboard.config_flow.MerakiDashboardApi.async_get_network_clients",
        AsyncMock(
            return_value=[
                {
                    "mac": "22:33:44:55:66:77",
                    "description": "Miles phone",
                }
            ]
        ),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_TRACK_CLIENTS: False,
                CONF_TRACK_BLUETOOTH_CLIENTS: False,
                CONF_TRACK_INFRASTRUCTURE_DEVICES: True,
                CONF_INCLUDED_CLIENTS: ["22:33:44:55:66:77"],
            },
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_TRACK_CLIENTS: False,
        CONF_TRACK_BLUETOOTH_CLIENTS: False,
        CONF_TRACK_INFRASTRUCTURE_DEVICES: True,
        CONF_INCLUDED_CLIENTS: ["22:33:44:55:66:77"],
    }
