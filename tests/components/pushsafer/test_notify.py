"""Tests for the Pushsafer notify platform."""

from http import HTTPStatus
from unittest.mock import patch

import requests

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


def _response(body: bytes) -> requests.Response:
    """Return a Pushsafer API response."""
    response = requests.Response()
    response.status_code = HTTPStatus.OK
    response._content = body
    return response


async def test_send_message_with_unparsable_response(hass: HomeAssistant) -> None:
    """Test a sent message doesn't fail on a response that isn't a single JSON object."""
    assert await async_setup_component(
        hass,
        NOTIFY_DOMAIN,
        {
            NOTIFY_DOMAIN: [
                {"platform": "pushsafer", "name": "pushsafer", "private_key": "key"}
            ]
        },
    )
    await hass.async_block_till_done()

    # Pushsafer can answer with more than one JSON object in a single response
    with patch(
        "homeassistant.components.pushsafer.notify.requests.post",
        return_value=_response(
            b'{"status":1,"success":"message transmitted"}{"available":{"a":{"x":"y"}}}'
        ),
    ) as mock_post:
        await hass.services.async_call(
            NOTIFY_DOMAIN, "pushsafer", {"message": "Hello"}, blocking=True
        )

    mock_post.assert_called_once()
