"""Test cloud subscription functions."""
import asyncio
from unittest.mock import AsyncMock, Mock

from hass_nabucasa import Cloud
import pytest

from homeassistant.components.cloud.subscription import (
    async_migrate_paypal_agreement,
    async_subscription_info,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(name="mocked_cloud")
async def mocked_cloud_object(hass: HomeAssistant) -> Cloud:
    """Mock cloud object."""
    return Mock(
        accounts_server="accounts.nabucasa.com",
        auth=Mock(async_check_token=AsyncMock()),
        websession=async_get_clientsession(hass),
    )


async def test_fetching_subscription_with_timeout_error(
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
    mocked_cloud: Cloud,
) -> None:
    """Test that we handle timeout error."""
    aioclient_mock.get(
        "https://accounts.nabucasa.com/payments/subscription_info",
        exc=asyncio.TimeoutError(),
    )

    assert await async_subscription_info(mocked_cloud) is None
    assert (
        "A timeout of 10 was reached while trying to fetch subscription information"
        in caplog.text
    )


async def test_migrate_paypal_agreement_with_timeout_error(
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
    mocked_cloud: Cloud,
) -> None:
    """Test that we handle timeout error."""
    aioclient_mock.post(
        "https://accounts.nabucasa.com/payments/migrate_paypal_agreement",
        exc=asyncio.TimeoutError(),
    )

    assert await async_migrate_paypal_agreement(mocked_cloud) is None
    assert (
        "A timeout of 10 was reached while trying to start agreement migration"
        in caplog.text
    )
