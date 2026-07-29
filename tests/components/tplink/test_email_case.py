"""Tests for the TP-Link e-mail case-detection helper."""

import pytest

from homeassistant.components.tplink._email_case import (
    async_get_canonical_username,
    suggest_username_case,
)
from homeassistant.core import HomeAssistant

from tests.test_util.aiohttp import AiohttpClientMocker

_CLOUD_URL = "https://wap.tplinkcloud.com"


@pytest.mark.parametrize(
    ("entered", "canonical", "expected"),
    [
        ("jdoe@example.com", "Jdoe@example.com", "Jdoe@example.com"),
        ("JDOE@example.com", "jdoe@example.com", "jdoe@example.com"),
        ("jdoe@example.com", "jdoe@example.com", None),
        ("jdoe@example.com", None, None),
        ("jdoe@example.com", "someone@else.com", None),
    ],
)
def test_suggest_username_case(
    entered: str, canonical: str | None, expected: str | None
) -> None:
    """Only a pure case-difference yields a suggestion."""
    assert suggest_username_case(entered, canonical) == expected


async def test_get_canonical_username_success(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The canonical e-mail is read from the cloud login response."""
    aioclient_mock.post(
        _CLOUD_URL,
        json={"error_code": 0, "result": {"email": "Jdoe@example.com"}},
    )
    result = await async_get_canonical_username(hass, "jdoe@example.com", "pw")
    assert result == "Jdoe@example.com"


async def test_get_canonical_username_cloud_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A cloud error (e.g. wrong password / MFA) yields None, not a raise."""
    aioclient_mock.post(_CLOUD_URL, json={"error_code": -20601})
    assert await async_get_canonical_username(hass, "jdoe@example.com", "pw") is None


async def test_get_canonical_username_network_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A network failure yields None, not a raise."""
    aioclient_mock.post(_CLOUD_URL, exc=TimeoutError())
    assert await async_get_canonical_username(hass, "jdoe@example.com", "pw") is None
