"""Additional tests for NRGkick config flow edge cases."""

from __future__ import annotations

from ipaddress import ip_address
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.nrgkick.api import (
    NRGkickApiClientAuthenticationError,
    NRGkickApiClientError,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import create_mock_config_entry

# Reauth Flow Additional Tests


async def test_reauth_flow_invalid_auth(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test reauth flow with invalid authentication."""
    entry = create_mock_config_entry(
        domain="nrgkick",
        title="NRGkick Test",
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: "old_user",
            CONF_PASSWORD: "old_pass",
        },
        entry_id="test_entry",
        unique_id="TEST123456",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        "nrgkick",
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientAuthenticationError

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "wrong_user",
                CONF_PASSWORD: "wrong_pass",
            },
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_reauth_flow_unknown_exception(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test reauth flow with unexpected exception."""
    entry = create_mock_config_entry(
        domain="nrgkick",
        title="NRGkick Test",
        data={CONF_HOST: "192.168.1.100"},
        entry_id="test_entry",
        unique_id="TEST123456",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        "nrgkick",
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientError
    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientError

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "new_user",
                CONF_PASSWORD: "new_pass",
            },
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


# Options Flow Additional Tests


# Zeroconf Additional Tests


async def test_zeroconf_discovery_invalid_auth(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test zeroconf discovery with authentication error."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.100"),
        ip_addresses=[ip_address("192.168.1.100")],
        hostname="nrgkick.local.",
        name="NRGkick Test._nrgkick._tcp.local.",
        port=80,
        properties={
            "serial_number": "TEST123456",
            "device_name": "NRGkick Test",
            "json_api_enabled": "1",
        },
        type="_nrgkick._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        "nrgkick",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientAuthenticationError

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "zeroconf_auth"

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_USERNAME: "wrong_user",
                CONF_PASSWORD: "wrong_pass",
            },
        )

    assert result3["type"] == data_entry_flow.FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_auth"}


async def test_zeroconf_discovery_unknown_exception(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test zeroconf discovery with unexpected exception."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.100"),
        ip_addresses=[ip_address("192.168.1.100")],
        hostname="nrgkick.local.",
        name="NRGkick Test._nrgkick._tcp.local.",
        port=80,
        properties={
            "serial_number": "TEST123456",
            "device_name": "NRGkick Test",
            "json_api_enabled": "1",
        },
        type="_nrgkick._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        "nrgkick",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientError

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_zeroconf_fallback_to_default_name(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test zeroconf when device_name and model_type are missing."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.100"),
        ip_addresses=[ip_address("192.168.1.100")],
        hostname="nrgkick.local.",
        name="Unknown Device._nrgkick._tcp.local.",
        port=80,
        properties={
            "serial_number": "TEST123456",
            "json_api_enabled": "1",
            # No device_name
            # No model_type
        },
        type="_nrgkick._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        "nrgkick",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    # Should fallback to "NRGkick"
    assert result["description_placeholders"] == {
        "name": "NRGkick",
        "device_ip": "192.168.1.100",
    }
