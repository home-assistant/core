"""Tests for the RFM Gateway config flow."""

from __future__ import annotations

from ipaddress import ip_address
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components import rfm_gateway
from homeassistant.components.rfm_gateway.config_flow import RfmGatewayConfigFlow
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

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


@pytest.mark.parametrize(
    ("host", "hostname", "expected_host"),
    [
        pytest.param("192.0.2.12", "_http._tcp.local.", "192.0.2.12", id="raw-host-ip"),
        pytest.param(
            "_http._tcp.local.", "192.0.2.13", "192.0.2.13", id="raw-hostname-ip"
        ),
        pytest.param(
            "rfm-gateway.local.",
            "_http._tcp.local.",
            "rfm-gateway.local",
            id="raw-host-hostname",
        ),
        pytest.param(
            "_http._tcp.local.",
            "rfm-gateway.local.",
            "rfm-gateway.local",
            id="raw-hostname-hostname",
        ),
    ],
)
async def test_zeroconf_uses_raw_host_fallbacks(
    hass: HomeAssistant,
    host: str,
    hostname: str,
    expected_host: str,
) -> None:
    """Test zeroconf host fallback selection from raw host/hostname fields."""
    discovery = SimpleNamespace(
        ip_address=None,
        ip_addresses=[],
        host=host,
        hostname=hostname,
        name="RFM Gateway",
        properties={"model": "rfm-gateway"},
    )

    result = await hass.config_entries.flow.async_init(
        rfm_gateway.DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["description_placeholders"]["host"] == expected_host


async def test_zeroconf_confirm_aborts_without_discovered_host(
    hass: HomeAssistant,
) -> None:
    """Test zeroconf confirm aborts when discovery host was not set."""
    flow = RfmGatewayConfigFlow()
    flow.hass = hass
    flow.context = {}

    result = await flow.async_step_zeroconf_confirm()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_config_flow_client_wrapper_methods(hass: HomeAssistant) -> None:
    """Test internal client wrapper methods on the config flow."""
    flow = RfmGatewayConfigFlow()
    flow.hass = hass

    with patch(
        "homeassistant.components.rfm_gateway.RfmGatewayClient.async_get_capabilities",
        new=AsyncMock(return_value=_mock_caps()),
    ) as mock_get_capabilities:
        capabilities = await flow._async_get_capabilities(TEST_HOST)
        await flow._async_validate_host(TEST_HOST)

    assert capabilities.device_name == "RFM Gateway"
    assert mock_get_capabilities.await_count == 2


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
    assert flow._normalize_host("   ") == ""
    assert flow._normalize_host("example.local.") == "example.local"
    assert flow._normalize_host("[2001:db8::1]") == "2001:db8::1"
    assert flow._normalize_host("[2001:db8::1") == "[2001:db8::1"
    assert flow._normalize_host("example.com:8080") == "example.com"
    assert flow._normalize_host("example.com") == "example.com"

    assert flow._is_ip_address("192.0.2.10")
    assert not flow._is_ip_address("")
    assert not flow._is_ip_address("example.local")

    assert flow._preferred_discovery_ip("") is None
    assert flow._preferred_discovery_ip("invalid") is None
    assert flow._preferred_discovery_ip("192.0.2.10") == "192.0.2.10"
    assert flow._preferred_discovery_ip("fe80::1") is None
    assert flow._preferred_discovery_ip("2001:db8::1") == "2001:db8::1"

    assert not flow._is_usable_discovery_host("")
    assert not flow._is_usable_discovery_host("192.0.2.10")
    assert not flow._is_usable_discovery_host("_http._tcp.local")
    assert not flow._is_usable_discovery_host("foo._bar")
    assert not flow._is_usable_discovery_host("foo_bar")
    assert flow._is_usable_discovery_host("rfm-gateway.local")
