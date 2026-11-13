"""Test talking to the Voice app."""

from typing import Any

import aiohttp
import pytest
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.voice_support.client import (
    AppInfo,
    InvalidResponseError,
    UnsupportedVersionError,
    VoiceSupportClient,
    normalize_wake_word,
)
from homeassistant.core import HomeAssistant

from .conftest import HOST, INFO, INFO_URL, PORT


@pytest.mark.parametrize(
    ("wake_word", "expected"),
    [
        pytest.param("Okay Nabu", "okay_nabu", id="phrase"),
        pytest.param("okay-nabu", "okay_nabu", id="dashes"),
        pytest.param("okay_nabu", "okay_nabu", id="id"),
        pytest.param("Hey, Jarvis!", "hey_jarvis", id="punctuation"),
    ],
)
def test_normalize_wake_word(wake_word: str, expected: str) -> None:
    """Test the spellings of a wake word come out the same."""
    assert normalize_wake_word(wake_word) == expected


@pytest.mark.parametrize(
    ("host", "url"),
    [
        pytest.param(HOST, INFO_URL, id="ipv4"),
        pytest.param("2001:db8::1", f"http://[2001:db8::1]:{PORT}/info", id="ipv6"),
    ],
)
async def test_update_info(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, host: str, url: str
) -> None:
    """Test reading what the app says about itself."""
    aioclient_mock.get(url, json=INFO)
    client = VoiceSupportClient(hass, host, PORT)
    assert client.info is None

    info = await client.async_update_info()

    assert info.name == "Voice"
    assert info.version == "1.0.0"
    assert info.wake_words == {"okay_nabu": "okay nabu"}
    assert client.info is info


async def test_update_info_wrong_api_version(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test an app speaking another protocol version cannot be used."""
    aioclient_mock.get(INFO_URL, json={**INFO, "api_version": 2})
    client = VoiceSupportClient(hass, HOST, PORT)
    client.info = AppInfo.from_json(INFO)

    with pytest.raises(UnsupportedVersionError) as err:
        await client.async_update_info()

    assert err.value.info.api_version == 2
    assert str(err.value) == "Voice 1.0.0 speaks protocol version 2, not 1"
    assert client.info is None


@pytest.mark.parametrize(
    ("response", "error"),
    [
        pytest.param(
            {"exc": aiohttp.ClientError}, aiohttp.ClientError, id="unreachable"
        ),
        pytest.param({"status": 500}, aiohttp.ClientResponseError, id="error"),
        pytest.param(
            {"text": "not json", "headers": {"Content-Type": "application/json"}},
            InvalidResponseError,
            id="garbage",
        ),
        pytest.param(
            {"json": {"name": "Voice", "api_version": 1}},
            InvalidResponseError,
            id="incomplete",
        ),
        pytest.param(
            {"json": {**INFO, "wake_words": [{}]}},
            InvalidResponseError,
            id="nameless_wake_word",
        ),
        pytest.param(
            {"json": {**INFO, "wake_words": [{"id": None}]}},
            InvalidResponseError,
            id="wake_word_id_not_text",
        ),
        *[
            pytest.param(
                {"json": {**INFO, field: value}}, InvalidResponseError, id=name
            )
            for field, value, name in (
                ("name", None, "invalid_name"),
                ("version", 1, "invalid_version"),
                ("api_version", "1", "invalid_api_version"),
                ("api_version", True, "boolean_api_version"),
                ("wake_words", [None], "invalid_wake_word"),
                ("wake_words", [{"id": "okay_nabu", "phrase": 42}], "invalid_phrase"),
            )
        ],
        pytest.param(
            {"json": {**INFO, "wake_words": "okay nabu"}},
            InvalidResponseError,
            id="wrong_type",
        ),
    ],
)
async def test_update_info_failure(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    response: dict[str, Any],
    error: type[Exception],
) -> None:
    """Test an app that cannot be read, or breaks the contract, is forgotten."""
    aioclient_mock.get(INFO_URL, **response)
    client = VoiceSupportClient(hass, HOST, PORT)
    client.info = AppInfo.from_json(INFO)

    with pytest.raises(error):
        await client.async_update_info()

    assert client.info is None


@pytest.mark.parametrize("error", [AttributeError, KeyError, TypeError, ValueError])
async def test_update_info_unexpected_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, error: type[Exception]
) -> None:
    """Test errors outside response parsing are not handled as client failures."""
    aioclient_mock.get(INFO_URL, exc=error)
    client = VoiceSupportClient(hass, HOST, PORT)

    with pytest.raises(error):
        await client.async_update_info()


@pytest.mark.parametrize(
    "wake_word", [{"id": "okay_nabu"}, {"id": "okay_nabu", "phrase": None}]
)
async def test_update_info_optional_phrase(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    wake_word: dict[str, str | None],
) -> None:
    """Test optional phrases and extra response fields are accepted."""
    aioclient_mock.get(
        INFO_URL, json={**INFO, "wake_words": [wake_word], "extra": True}
    )
    client = VoiceSupportClient(hass, HOST, PORT)

    info = await client.async_update_info()

    assert info.wake_words == {"okay_nabu": None}
