"""Tests for the Withings component."""
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock
from urllib.parse import urlparse

import pytest
from withings_api.common import NotifyAppli

from homeassistant.components.webhook import async_generate_url
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import setup_integration
from .conftest import WEBHOOK_ID

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import ClientSessionGenerator


async def test_data_manager_webhook_subscription(
    hass: HomeAssistant,
    withings: AsyncMock,
    disable_webhook_delay,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test data manager webhook subscriptions."""
    await setup_integration(hass, config_entry)
    await hass_client_no_auth()
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()

    assert withings.notify_subscribe.call_count == 4

    webhook_url = "http://example.local:8123/api/webhook/55a7335ea8dee830eed4ef8f84cda8f6d80b83af0847dc74032e86120bffed5e"

    withings.notify_subscribe.assert_any_call(webhook_url, NotifyAppli.WEIGHT)
    withings.notify_subscribe.assert_any_call(webhook_url, NotifyAppli.CIRCULATORY)
    withings.notify_subscribe.assert_any_call(webhook_url, NotifyAppli.ACTIVITY)
    withings.notify_subscribe.assert_any_call(webhook_url, NotifyAppli.SLEEP)

    withings.notify_revoke.assert_any_call(webhook_url, NotifyAppli.BED_IN)
    withings.notify_revoke.assert_any_call(webhook_url, NotifyAppli.BED_OUT)


@pytest.mark.parametrize(
    "method",
    [
        "PUT",
        "HEAD",
    ],
)
async def test_requests(
    hass: HomeAssistant,
    withings: AsyncMock,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    method: str,
    disable_webhook_delay,
) -> None:
    """Test we handle request methods Withings sends."""
    await setup_integration(hass, config_entry)
    client = await hass_client_no_auth()
    webhook_url = async_generate_url(hass, WEBHOOK_ID)

    response = await client.request(
        method=method,
        path=urlparse(webhook_url).path,
    )
    assert response.status == 200


@pytest.mark.parametrize(
    ("body", "expected_code"),
    [
        [{"userid": 0, "appli": NotifyAppli.WEIGHT.value}, 0],  # Success
        [{"userid": None, "appli": 1}, 0],  # Success, we ignore the user_id.
        [{}, 12],  # No request body.
        [{"userid": "GG"}, 20],  # appli not provided.
        [{"userid": 0}, 20],  # appli not provided.
        [{"userid": 0, "appli": 99}, 21],  # Invalid appli.
        [
            {"userid": 11, "appli": NotifyAppli.WEIGHT.value},
            0,
        ],  # Success, we ignore the user_id
    ],
)
async def test_webhook_post(
    hass: HomeAssistant,
    withings: AsyncMock,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    disable_webhook_delay,
    body: dict[str, Any],
    expected_code: int,
    current_request_with_host: None,
) -> None:
    """Test webhook callback."""
    await setup_integration(hass, config_entry)
    client = await hass_client_no_auth()
    webhook_url = async_generate_url(hass, WEBHOOK_ID)

    resp = await client.post(urlparse(webhook_url).path, data=body)

    # Wait for remaining tasks to complete.
    await hass.async_block_till_done()

    data = await resp.json()
    resp.close()

    assert data["code"] == expected_code
