"""Tests for the TuneBlade Remote config flow."""

from typing import Any
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from homeassistant import config_entries
from homeassistant.components.tuneblade_remote.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_user_flow_success(hass: HomeAssistant, mock_tuneblade_api: Any) -> None:
    """Test successful user setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] == "form"

    with patch(
        "homeassistant.components.tuneblade_remote.config_flow.TuneBladeConfigFlow._async_abort_entries_match",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "localhost", CONF_PORT: 54412},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "TuneBlade (localhost)"
    assert result["data"] == {CONF_HOST: "localhost", CONF_PORT: 54412}


@pytest.mark.asyncio
async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test user setup with connection error."""
    with patch(
        "homeassistant.components.tuneblade_remote.config_flow.TuneBladeApiClient",
    ) as mock_client:
        instance = mock_client.return_value
        instance.async_get_data.side_effect = aiohttp.ClientError()

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["type"] == "form"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "localhost", CONF_PORT: 54412},
        )

        assert result["type"] == "form"
        assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_user_flow_already_configured(hass: HomeAssistant) -> None:
    """Test user flow aborts if already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="TuneBlade (localhost)",
        data={CONF_HOST: "localhost", CONF_PORT: 54412},
        unique_id="TuneBlade_localhost_54412",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.tuneblade_remote.config_flow.TuneBladeApiClient",
    ) as mock_client:
        mock_client.return_value.async_get_data = AsyncMock(
            return_value={"some": "data"}
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "localhost", CONF_PORT: 54412},
        )

        assert result["type"] == "abort"
        assert result["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_zeroconf_success(hass: HomeAssistant, mock_tuneblade_api: Any) -> None:
    """Test successful zeroconf discovery flow."""
    discovery_info = ZeroconfServiceInfo(
        ip_address="127.0.0.1",
        ip_addresses=["127.0.0.1"],
        port=54412,
        hostname="tuneblade.local.",
        name="TuneBlade@localhost",
        type="_tuneblade._tcp.local.",
        properties={},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] == "form"
    assert result["step_id"] == "confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "TuneBlade"
    assert result2["data"] == {
        "host": "127.0.0.1",
        "port": 54412,
        "name": "TuneBlade",
    }


@pytest.mark.asyncio
async def test_zeroconf_cannot_connect(hass: HomeAssistant) -> None:
    """Test zeroconf discovery with connection failure."""
    with patch(
        "homeassistant.components.tuneblade_remote.config_flow.TuneBladeApiClient",
    ) as mock_client:
        instance = mock_client.return_value
        instance.async_get_data.side_effect = Exception("Connection failed")

        discovery_info = ZeroconfServiceInfo(
            ip_address="127.0.0.1",
            ip_addresses=["127.0.0.1"],
            port=54412,
            hostname="tuneblade.local.",
            name="TuneBlade@localhost",
            type="_tuneblade._tcp.local.",
            properties={},
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=discovery_info,
        )

        assert result["type"] == "abort"
        assert result["reason"] == "cannot_connect"


@pytest.mark.asyncio
async def test_zeroconf_already_configured(hass: HomeAssistant) -> None:
    """Test zeroconf aborts if unique ID is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="TuneBlade",
        data={"host": "127.0.0.1", "port": 54412, "name": "TuneBlade"},
        unique_id="TuneBlade_127.0.0.1_54412",
    )
    entry.add_to_hass(hass)

    discovery_info = ZeroconfServiceInfo(
        ip_address="127.0.0.1",
        ip_addresses=["127.0.0.1"],
        port=54412,
        hostname="tuneblade.local.",
        name="TuneBlade@localhost",
        type="_tuneblade._tcp.local.",
        properties={},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
