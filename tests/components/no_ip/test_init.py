"""Test the NO-IP component."""
from datetime import timedelta

import pytest

from homeassistant.components import no_ip
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker

import asyncio
import aiohttp

DOMAIN = "test.example.com"

PASSWORD = "xyz789"

UPDATE_URL = no_ip.UPDATE_URL

USERNAME = "abc@123.com"


@pytest.fixture
def setup_no_ip(hass, aioclient_mock):
    """Fixture that sets up NO-IP."""
    aioclient_mock.get(UPDATE_URL, params={"hostname": DOMAIN}, text="good 0.0.0.0")

    hass.loop.run_until_complete(
        async_setup_component(
            hass,
            no_ip.DOMAIN,
            {
                no_ip.DOMAIN: [{
                    "domain": DOMAIN,
                    "username": USERNAME,
                    "password": PASSWORD,
                }]
            },
        )
    )


async def test_setup_1_domain(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Test setup works if update passes."""
    aioclient_mock.get(UPDATE_URL, params={"hostname": DOMAIN}, text="nochg 0.0.0.0")

    result = await async_setup_component(
        hass,
        no_ip.DOMAIN,
        {no_ip.DOMAIN: [{"domain": DOMAIN, "username": USERNAME, "password": PASSWORD}]},
    )
    assert result
    assert aioclient_mock.call_count == 0

    async_fire_time_changed(hass, utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()
    assert result
    assert aioclient_mock.call_count == 1

async def test_setup_2_domain(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Test setup works if update passes."""
    aioclient_mock.get(UPDATE_URL, params={"hostname": DOMAIN}, text="nochg 0.0.0.0")

    result = await async_setup_component(
        hass,
        no_ip.DOMAIN,
        {no_ip.DOMAIN: [{"domain": DOMAIN, "username": USERNAME, "password": PASSWORD}, {"domain": DOMAIN, "username": USERNAME, "password": PASSWORD}]},
    )
    assert result
    assert aioclient_mock.call_count == 0

    async_fire_time_changed(hass, utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()
    assert result
    assert aioclient_mock.call_count == 2

async def test_setup_fails_if_wrong_auth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup fails if first update fails through wrong authentication."""
    aioclient_mock.get(UPDATE_URL, params={"hostname": DOMAIN}, text="badauth")

    result = await async_setup_component(
        hass,
        no_ip.DOMAIN,
        {no_ip.DOMAIN: [{"domain": DOMAIN, "username": USERNAME, "password": PASSWORD}]},
    )
    assert result
    assert aioclient_mock.call_count == 0

    async_fire_time_changed(hass, utcnow() + timedelta(minutes=5))
    result_block = await hass.async_block_till_done()
    assert not result_block
    assert aioclient_mock.call_count == 1

async def test_setup_fails_if_timeout(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup fails if first update fails through wrong authentication."""
    aioclient_mock.get(UPDATE_URL, params={"hostname": DOMAIN}, text="badauth", exc=asyncio.TimeoutError())

    result = await async_setup_component(
        hass,
        no_ip.DOMAIN,
        {no_ip.DOMAIN: [{"domain": DOMAIN, "username": USERNAME, "password": PASSWORD}]},
    )
    assert result
    assert aioclient_mock.call_count == 0

    async_fire_time_changed(hass, utcnow() + timedelta(minutes=5))
    result_block = await hass.async_block_till_done()
    assert not result_block
    assert aioclient_mock.call_count == 1

async def test_setup_fails_if_client_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup fails if first update fails through wrong authentication."""
    aioclient_mock.get(UPDATE_URL, params={"hostname": DOMAIN}, text="badauth", exc=aiohttp.ClientError())

    result = await async_setup_component(
        hass,
        no_ip.DOMAIN,
        {no_ip.DOMAIN: [{"domain": DOMAIN, "username": USERNAME, "password": PASSWORD}]},
    )
    assert result
    assert aioclient_mock.call_count == 0

    async_fire_time_changed(hass, utcnow() + timedelta(minutes=5))
    result_block = await hass.async_block_till_done()
    assert not result_block
    assert aioclient_mock.call_count == 1
