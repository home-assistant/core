"""Tests for the OAuth 2.0 helpers."""

from multidict import CIMultiDict
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import oauth2

from tests.test_util.aiohttp import AiohttpClientMocker

ACCESS_TOKEN = "mock-access-token"


@pytest.mark.parametrize("code_verifier_length", [40, 129])
def test_generate_code_verifier_invalid_length(code_verifier_length: int) -> None:
    """Test generate_code_verifier with an invalid length."""
    with pytest.raises(ValueError):
        oauth2.generate_code_verifier(code_verifier_length)


@pytest.mark.parametrize("code_verifier", ["", "yyy", "a" * 129])
def test_compute_code_challenge_invalid_code_verifier(code_verifier: str) -> None:
    """Test compute_code_challenge with an invalid code_verifier."""
    with pytest.raises(ValueError):
        oauth2.compute_code_challenge(code_verifier)


@pytest.mark.parametrize(
    "header_name",
    [
        pytest.param("Authorization", id="canonical_casing"),
        pytest.param("authorization", id="lowercase"),
    ],
)
async def test_oauth2_request_replaces_caller_authorization_header(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    header_name: str,
) -> None:
    """Test the token replaces a caller supplied Authorization header."""
    aioclient_mock.post("https://example.com", status=201)

    await oauth2.async_oauth2_request(
        hass,
        {"access_token": ACCESS_TOKEN},
        "post",
        "https://example.com",
        headers={header_name: "Bearer caller supplied"},
    )

    assert len(aioclient_mock.mock_calls) == 1
    headers = CIMultiDict(aioclient_mock.mock_calls[0][3])

    # The token must not be sent as a second Authorization header
    assert headers.getall("Authorization") == [f"Bearer {ACCESS_TOKEN}"]
