"""Test that TTL is forwarded into PushoverAPI.send_message()."""

from unittest.mock import patch

import pytest

from homeassistant.components.pushover.const import ATTR_TTL
from homeassistant.components.pushover.notify import PushoverNotificationService
from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
def pushover_api_mock():
    """Patch out the real PushoverAPI so we can inspect calls."""
    with patch("homeassistant.components.pushover.notify.PushoverAPI") as mock_api_cls:
        yield mock_api_cls.return_value


async def test_ttl_passed_to_send_message(
    hass: HomeAssistant, pushover_api_mock
) -> None:
    """When you pass ttl in data, it ends up in the correct position."""
    # 1) Construct the service
    #    The constructor args are: (hass, entry, creds, platform)
    #    We only care that it wires self.pushover = PushoverAPI(...)
    service = PushoverNotificationService(
        hass,
        entry={},
        creds={"user_key": "USER123", "app_token": "APP456"},
        platform=None,
    )

    # 2) Call async_send_message with a ttl of 300 seconds
    await service.async_send_message(
        message="Test TTL",
        data={ATTR_TTL: 300},
        targets=["device_a"],
    )

    # 3) Ensure PushoverAPI.send_message got called exactly once
    assert pushover_api_mock.send_message.call_count == 1

    # 4) Grab the positional args it was called with
    #    Signature is:
    #      send_message(user, message, device, title, url, url_title, image,
    #                   priority, retry, expire, callback_url, timestamp,
    #                   sound, html, ttl)
    _, args, _ = pushover_api_mock.send_message.mock_calls[0]

    # 5) TTL is the last positional argument (index -1)
    assert args[-1] == 300
