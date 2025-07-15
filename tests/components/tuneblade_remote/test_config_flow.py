"""Test the TuneBlade Remote config flow."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.tuneblade_remote.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo


@pytest.mark.asyncio
async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test a successful user config flow."""
    mock_devices: dict[str, Any] = {"MASTER": {"name": "Master"}}

    with patch(
        "homeassistant.components.tuneblade_remote.config_flow.TuneBladeApiClient.async_get_data",
        new_callable=AsyncMock,
        return_value=mock_devices,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
        )
        assert result["type"] == FlowResultType.FORM

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "localhost", CONF_PORT: 54412},
        )
        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["data"] == {CONF_HOST: "localhost", CONF_PORT: 54412}


@pytest.mark.asyncio
async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test user flow with connection failure."""
    with patch(
        "homeassistant.components.tuneblade_remote.config_flow.TuneBladeApiClient.async_get_data",
        new_callable=AsyncMock,
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
        )
        assert result["type"] == FlowResultType.FORM

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "localhost", CONF_PORT: 54412},
        )
        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_zeroconf_success(hass: HomeAssistant) -> None:
    """Test a successful zeroconf discovery flow."""
    discovery_info = ZeroconfServiceInfo(
        name="Master@tuneblade._http._tcp.local.",
        type_="_http._tcp.local.",
        properties={},
        address="192.168.1.10",
        port=54412,
        hostname="Master.local.",
    )

    mock_devices: dict[str, Any] = {"MASTER": {"name": "Master"}}

    with patch(
        "homeassistant.components.tuneblade_remote.config_flow.TuneBladeApiClient.async_get_data",
        new_callable=AsyncMock,
        return_value=mock_devices,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "zeroconf"},
            data=discovery_info,
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "confirm"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )
        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["data"] == {
            "host": discovery_info.address,
            "port": discovery_info.port,
            "name": "Master",
        }


@pytest.mark.asyncio
async def test_zeroconf_cannot_connect(hass: HomeAssistant) -> None:
    """Test zeroconf discovery fails to connect."""
    discovery_info = ZeroconfServiceInfo(
        name="Master@tuneblade._http._tcp.local.",
        type_="_http._tcp.local.",
        properties={},
        address="192.168.1.10",
        port=54412,
        hostname="Master.local.",
    )

    with patch(
        "homeassistant.components.tuneblade_remote.config_flow.TuneBladeApiClient.async_get_data",
        new_callable=AsyncMock,
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "zeroconf"},
            data=discovery_info,
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "cannot_connect"
