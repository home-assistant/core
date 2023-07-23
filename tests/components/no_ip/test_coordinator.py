"""Tests for coordinator No-IP.com integration."""
from __future__ import annotations

import asyncio

import aiohttp
import pytest

from homeassistant.components import no_ip
from homeassistant.components.no_ip import DOMAIN, NoIPDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DOMAIN,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.asyncio
async def test_async_update_data_success(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the successful update of data."""
    aioclient_mock.get(
        no_ip.const.UPDATE_URL,
        text="good 192.168.1.1",
    )

    entry = ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="test",
        data={
            CONF_IP_ADDRESS: "1.2.3.4",
            CONF_DOMAIN: "test.example.com",
            CONF_USERNAME: "abc@123.com",
            CONF_PASSWORD: "xyz789",
        },
        source="test",
        options={},
    )

    # Create a coordinator instance using the ConfigEntry
    coordinator = NoIPDataUpdateCoordinator(hass, entry)

    # Fetch the updated data using the coordinator
    data = await coordinator._async_update_data()

    assert data == {
        CONF_IP_ADDRESS: "192.168.1.1",
        CONF_DOMAIN: "test.example.com",
        CONF_USERNAME: "abc@123.com",
        CONF_PASSWORD: "xyz789",
    }


@pytest.mark.asyncio
async def test_async_update_data_failure(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the failure of data update."""
    aioclient_mock.get(
        no_ip.const.UPDATE_URL,
        text="nohost",
    )

    entry = ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="test",
        data={
            CONF_DOMAIN: "test.example.com",
            CONF_USERNAME: "abc@123.com",
            CONF_PASSWORD: "xyz789",
        },
        source="test",
        options={},
    )

    # Create a coordinator instance using the ConfigEntry
    coordinator = NoIPDataUpdateCoordinator(hass, entry)

    data = await coordinator._async_update_data()
    assert data["ip_address"] is None


@pytest.mark.asyncio
async def test_async_update_data_client_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the client error during data update."""
    aioclient_mock.get(no_ip.const.UPDATE_URL, text="nohost", exc=aiohttp.ClientError)

    entry = ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="test",
        data={
            CONF_IP_ADDRESS: "1.2.3.4",
            CONF_DOMAIN: "test.example.com",
            CONF_USERNAME: "abc@123.com",
            CONF_PASSWORD: "xyz789",
        },
        source="test",
        options={},
    )

    # Create a coordinator instance using the ConfigEntry
    coordinator = NoIPDataUpdateCoordinator(hass, entry)
    with pytest.raises(aiohttp.ClientError):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_async_update_data_timeout(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the timeout during data update."""
    aioclient_mock.get(
        no_ip.const.UPDATE_URL,
        text="nohost",
        exc=asyncio.TimeoutError(),
    )
    entry = ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="test",
        data={
            CONF_IP_ADDRESS: "1.2.3.4",
            CONF_DOMAIN: "test.example.com",
            CONF_USERNAME: "abc@123.com",
            CONF_PASSWORD: "xyz789",
        },
        source="test",
        options={},
    )
    # Create a coordinator instance using the ConfigEntry
    coordinator = NoIPDataUpdateCoordinator(hass, entry)
    with pytest.raises(asyncio.TimeoutError):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_async_update_data_unknow(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the timeout during data update."""
    aioclient_mock.get(
        no_ip.const.UPDATE_URL,
        text="nohost",
        exc=Exception,
    )
    entry = ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="test",
        data={
            CONF_IP_ADDRESS: "1.2.3.4",
            CONF_DOMAIN: "test.example.com",
            CONF_USERNAME: "abc@123.com",
            CONF_PASSWORD: "xyz789",
        },
        source="test",
        options={},
    )
    # Create a coordinator instance using the ConfigEntry
    coordinator = NoIPDataUpdateCoordinator(hass, entry)
    with pytest.raises(Exception):
        await coordinator._async_update_data()
