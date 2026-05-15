"""Tests for the RFM Gateway config flow."""

from __future__ import annotations

from ipaddress import ip_address
from unittest.mock import AsyncMock, patch

from homeassistant.components import rfm_gateway
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
