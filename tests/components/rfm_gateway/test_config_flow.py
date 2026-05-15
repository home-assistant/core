"""Tests for the RFM Gateway config flow."""

from __future__ import annotations

from ipaddress import ip_address
from unittest.mock import AsyncMock, patch

from homeassistant.components import rfm_gateway
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.components.rfm_gateway.config_flow import RfmGatewayConfigFlow

TEST_HOST = "192.0.2.10"
TEST_OTHER_HOST = "192.0.2.11"


def _mock_caps() -> rfm_gateway.RfmCapabilities:
    return rfm_gateway.RfmCapabilities(
        supported_frequency_ranges=[(433050000, 434790000)],
        supported_modulations=["ook"],
        device_name="RFM Gateway",
    )


async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test successful manual setup."""
    with (
        patch(
            "homeassistant.components.rfm_gateway.config_flow.RfmGatewayConfigFlow._async_get_capabilities",
            new=AsyncMock(return_value=_mock_caps()),
        ),
        patch(
            "homeassistant.components.rfm_gateway.RfmGatewayClient.async_get_capabilities",
            new=AsyncMock(return_value=_mock_caps()),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            rfm_gateway.DOMAIN,
            context={"source": SOURCE_USER},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={rfm_gateway.CONF_HOST: TEST_HOST},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "RFM Gateway"
    assert result["data"] == {rfm_gateway.CONF_HOST: TEST_HOST}


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test manual setup connection failure."""
    with patch(
        "homeassistant.components.rfm_gateway.config_flow.RfmGatewayConfigFlow._async_get_capabilities",
        new=AsyncMock(side_effect=rfm_gateway.RfmGatewayConnectionError("boom")),
    ):
        result = await hass.config_entries.flow.async_init(
            rfm_gateway.DOMAIN,
            context={"source": SOURCE_USER},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={rfm_gateway.CONF_HOST: TEST_HOST},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_invalid_response(hass: HomeAssistant) -> None:
    """Test manual setup protocol failure."""
    with patch(
        "homeassistant.components.rfm_gateway.config_flow.RfmGatewayConfigFlow._async_get_capabilities",
        new=AsyncMock(side_effect=rfm_gateway.RfmGatewayProtocolError("boom")),
    ):
        result = await hass.config_entries.flow.async_init(
            rfm_gateway.DOMAIN,
            context={"source": SOURCE_USER},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={rfm_gateway.CONF_HOST: TEST_HOST},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_response"}


async def test_zeroconf_flow_success(hass: HomeAssistant) -> None:
    """Test successful zeroconf setup."""
    discovery = ZeroconfServiceInfo(
        ip_address=ip_address(TEST_HOST),
        ip_addresses=[ip_address(TEST_HOST)],
        hostname="rfm-gateway.local.",
        name="RFM Gateway",
        port=80,
        properties={"model": "rfm-gateway"},
        type="_http._tcp.local.",
    )

    with (
        patch(
            "homeassistant.components.rfm_gateway.config_flow.RfmGatewayConfigFlow._async_get_capabilities",
            new=AsyncMock(return_value=_mock_caps()),
        ),
        patch(
            "homeassistant.components.rfm_gateway.RfmGatewayClient.async_get_capabilities",
            new=AsyncMock(return_value=_mock_caps()),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            rfm_gateway.DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data=discovery,
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "zeroconf_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {rfm_gateway.CONF_HOST: TEST_HOST}


async def test_zeroconf_flow_confirm_cannot_connect(hass: HomeAssistant) -> None:
    """Test zeroconf confirm when capability query cannot connect."""
    discovery = ZeroconfServiceInfo(
        ip_address=ip_address(TEST_HOST),
        ip_addresses=[ip_address(TEST_HOST)],
        hostname="rfm-gateway.local.",
        name="RFM Gateway",
        port=80,
        properties={"model": "rfm-gateway"},
        type="_http._tcp.local.",
    )

    with patch(
        "homeassistant.components.rfm_gateway.config_flow.RfmGatewayConfigFlow._async_get_capabilities",
        new=AsyncMock(side_effect=rfm_gateway.RfmGatewayConnectionError("boom")),
    ):
        result = await hass.config_entries.flow.async_init(
            rfm_gateway.DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data=discovery,
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_zeroconf_flow_confirm_invalid_response(hass: HomeAssistant) -> None:
    """Test zeroconf confirm when capability query returns invalid data."""
    discovery = ZeroconfServiceInfo(
        ip_address=ip_address(TEST_HOST),
        ip_addresses=[ip_address(TEST_HOST)],
        hostname="rfm-gateway.local.",
        name="RFM Gateway",
        port=80,
        properties={"model": "rfm-gateway"},
        type="_http._tcp.local.",
    )

    with patch(
        "homeassistant.components.rfm_gateway.config_flow.RfmGatewayConfigFlow._async_get_capabilities",
        new=AsyncMock(side_effect=rfm_gateway.RfmGatewayProtocolError("boom")),
    ):
        result = await hass.config_entries.flow.async_init(
            rfm_gateway.DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data=discovery,
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["errors"] == {"base": "invalid_response"}


async def test_zeroconf_prefers_ip_addresses_list_when_primary_not_usable(
    hass: HomeAssistant,
) -> None:
    """Test zeroconf host selection falls back to ip_addresses list."""
    discovery = ZeroconfServiceInfo(
        ip_address=ip_address("fe80::1"),
        ip_addresses=[None, ip_address(TEST_HOST)],
        hostname="rfm-gateway.local.",
        name="RFM Gateway",
        port=80,
        properties={"model": "rfm-gateway"},
        type="_http._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        rfm_gateway.DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"


async def test_zeroconf_aborts_when_no_usable_host(hass: HomeAssistant) -> None:
    """Test zeroconf aborts when no valid host candidate can be derived."""
    discovery = ZeroconfServiceInfo(
        ip_address=ip_address("fe80::1"),
        ip_addresses=[ip_address("fe80::2")],
        hostname="_http._tcp.local.",
        name="RFM Gateway",
        port=80,
        properties={"model": "rfm-gateway"},
        type="_http._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        rfm_gateway.DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_rfm_gateway"


async def test_zeroconf_ignores_non_rfm_device(hass: HomeAssistant) -> None:
    """Test zeroconf abort for unrelated devices."""
    discovery = ZeroconfServiceInfo(
        ip_address=ip_address(TEST_OTHER_HOST),
        ip_addresses=[ip_address(TEST_OTHER_HOST)],
        hostname="not-rfm.local.",
        name="Other Device",
        port=80,
        properties={"model": "other"},
        type="_http._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        rfm_gateway.DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_rfm_gateway"


def test_config_flow_helpers() -> None:
    """Test helper methods for host normalization and formatting."""
    flow = RfmGatewayConfigFlow

    assert flow._build_base_url("2001:db8::1") == "http://[2001:db8::1]:80"
    assert flow._build_base_url("192.0.2.10") == "http://192.0.2.10:80"

    assert flow._format_frequency_range([]) == ""
    assert flow._format_frequency_range([(433_050_000, 434_790_000)]) == (
        "Supported: 433-435 MHz"
    )

    assert flow._normalize_host(" 192.0.2.10 ") == "192.0.2.10"
    assert flow._normalize_host("example.local.") == "example.local"
    assert flow._normalize_host("[2001:db8::1]") == "2001:db8::1"
    assert flow._normalize_host("example.com:8080") == "example.com"

    assert flow._is_ip_address("192.0.2.10")
    assert not flow._is_ip_address("example.local")

    assert flow._preferred_discovery_ip("") is None
    assert flow._preferred_discovery_ip("invalid") is None
    assert flow._preferred_discovery_ip("192.0.2.10") == "192.0.2.10"
    assert flow._preferred_discovery_ip("fe80::1") is None

    assert not flow._is_usable_discovery_host("")
    assert not flow._is_usable_discovery_host("_http._tcp.local")
    assert not flow._is_usable_discovery_host("foo._bar")
    assert not flow._is_usable_discovery_host("foo_bar")
    assert flow._is_usable_discovery_host("rfm-gateway.local")
