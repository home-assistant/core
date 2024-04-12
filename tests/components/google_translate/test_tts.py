"""The tests for the Google speech platform."""

from __future__ import annotations

from collections.abc import Generator
from http import HTTPStatus
from typing import Any
from unittest.mock import MagicMock, patch

from gtts import gTTSError
import pytest

from homeassistant.components import tts
from homeassistant.components.google_translate.const import CONF_TLD, DOMAIN
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.config import async_process_ha_core_config
from homeassistant.const import ATTR_ENTITY_ID, CONF_PLATFORM
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_mock_service
from tests.components.tts.common import retrieve_media
from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
def tts_mutagen_mock_fixture_autouse(tts_mutagen_mock):
    """Mock writing tags."""


@pytest.fixture(autouse=True)
def mock_tts_cache_dir_autouse(mock_tts_cache_dir):
    """Mock the TTS cache dir with empty dir."""
    return mock_tts_cache_dir


@pytest.fixture
async def calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Mock media player calls."""
    return async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)


@pytest.fixture(autouse=True)
async def setup_internal_url(hass: HomeAssistant) -> None:
    """Set up internal url."""
    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:8123"}
    )


@pytest.fixture
def mock_gtts() -> Generator[MagicMock, None, None]:
    """Mock gtts."""
    with patch("homeassistant.components.google_translate.tts.gTTS") as mock_gtts:
        yield mock_gtts


@pytest.fixture(name="setup")
async def setup_fixture(
    hass: HomeAssistant,
    config: dict[str, Any],
    request: pytest.FixtureRequest,
) -> None:
    """Set up the test environment."""
    if request.param == "mock_setup":
        await mock_setup(hass, config)
    elif request.param == "mock_config_entry_setup":
        await mock_config_entry_setup(hass, config)
    else:
        raise RuntimeError("Invalid setup fixture")

    await hass.async_block_till_done()


@pytest.fixture(name="config")
def config_fixture() -> dict[str, Any]:
    """Return config."""
    return {}


async def mock_setup(hass: HomeAssistant, config: dict[str, Any]) -> None:
    """Mock setup."""
    assert await async_setup_component(
        hass, tts.DOMAIN, {tts.DOMAIN: {CONF_PLATFORM: DOMAIN} | config}
    )


async def mock_config_entry_setup(hass: HomeAssistant, config: dict[str, Any]) -> None:
    """Mock config entry setup."""
    default_config = {tts.CONF_LANG: "en", CONF_TLD: "com"}
    config_entry = MockConfigEntry(domain=DOMAIN, data=default_config | config)
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)


@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data"),
    [
        (
            "mock_setup",
            "google_translate_say",
            {
                ATTR_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
            },
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.google_en_com",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
            },
        ),
    ],
    indirect=["setup"],
)
async def test_tts_service(
    hass: HomeAssistant,
    mock_gtts: MagicMock,
    hass_client: ClientSessionGenerator,
    calls: list[ServiceCall],
    setup: str,
    tts_service: str,
    service_data: dict[str, Any],
) -> None:
    """Test tts service."""
    await hass.services.async_call(
        tts.DOMAIN,
        tts_service,
        service_data,
        blocking=True,
    )

    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.OK
    )
    assert len(mock_gtts.mock_calls) == 2

    assert mock_gtts.mock_calls[0][2] == {
        "text": "There is a person at the front door.",
        "lang": "en",
        "tld": "com",
    }


@pytest.mark.parametrize("config", [{tts.CONF_LANG: "de"}])
@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data"),
    [
        (
            "mock_setup",
            "google_translate_say",
            {
                ATTR_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
            },
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.google_de_com",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
            },
        ),
    ],
    indirect=["setup"],
)
async def test_service_say_german_config(
    hass: HomeAssistant,
    mock_gtts: MagicMock,
    hass_client: ClientSessionGenerator,
    calls: list[ServiceCall],
    setup: str,
    tts_service: str,
    service_data: dict[str, Any],
) -> None:
    """Test service call say with german code in the config."""
    await hass.services.async_call(
        tts.DOMAIN,
        tts_service,
        service_data,
        blocking=True,
    )

    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.OK
    )
    assert len(mock_gtts.mock_calls) == 2
    assert mock_gtts.mock_calls[0][2] == {
        "text": "There is a person at the front door.",
        "lang": "de",
        "tld": "com",
    }


@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data"),
    [
        (
            "mock_setup",
            "google_translate_say",
            {
                ATTR_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
                tts.ATTR_LANGUAGE: "de",
            },
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.google_en_com",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
                tts.ATTR_LANGUAGE: "de",
            },
        ),
    ],
    indirect=["setup"],
)
async def test_service_say_german_service(
    hass: HomeAssistant,
    mock_gtts: MagicMock,
    hass_client: ClientSessionGenerator,
    calls: list[ServiceCall],
    setup: str,
    tts_service: str,
    service_data: dict[str, Any],
) -> None:
    """Test service call say with german code in the service."""
    await hass.services.async_call(
        tts.DOMAIN,
        tts_service,
        service_data,
        blocking=True,
    )

    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.OK
    )
    assert len(mock_gtts.mock_calls) == 2
    assert mock_gtts.mock_calls[0][2] == {
        "text": "There is a person at the front door.",
        "lang": "de",
        "tld": "com",
    }


@pytest.mark.parametrize("config", [{tts.CONF_LANG: "en-uk"}])
@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data"),
    [
        (
            "mock_setup",
            "google_translate_say",
            {
                ATTR_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
            },
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.google_en_co_uk",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
            },
        ),
    ],
    indirect=["setup"],
)
async def test_service_say_en_uk_config(
    hass: HomeAssistant,
    mock_gtts: MagicMock,
    hass_client: ClientSessionGenerator,
    calls: list[ServiceCall],
    setup: str,
    tts_service: str,
    service_data: dict[str, Any],
) -> None:
    """Test service call say with en-uk code in the config."""
    await hass.services.async_call(
        tts.DOMAIN,
        tts_service,
        service_data,
        blocking=True,
    )

    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.OK
    )
    assert len(mock_gtts.mock_calls) == 2
    assert mock_gtts.mock_calls[0][2] == {
        "text": "There is a person at the front door.",
        "lang": "en",
        "tld": "co.uk",
    }


@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data"),
    [
        (
            "mock_setup",
            "google_translate_say",
            {
                ATTR_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
                tts.ATTR_LANGUAGE: "en-uk",
            },
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.google_en_com",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
                tts.ATTR_LANGUAGE: "en-uk",
            },
        ),
    ],
    indirect=["setup"],
)
async def test_service_say_en_uk_service(
    hass: HomeAssistant,
    mock_gtts: MagicMock,
    hass_client: ClientSessionGenerator,
    calls: list[ServiceCall],
    setup: str,
    tts_service: str,
    service_data: dict[str, Any],
) -> None:
    """Test service call say with en-uk code in the config."""
    await hass.services.async_call(
        tts.DOMAIN,
        tts_service,
        service_data,
        blocking=True,
    )

    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.OK
    )
    assert len(mock_gtts.mock_calls) == 2
    assert mock_gtts.mock_calls[0][2] == {
        "text": "There is a person at the front door.",
        "lang": "en",
        "tld": "co.uk",
    }


@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data"),
    [
        (
            "mock_setup",
            "google_translate_say",
            {
                ATTR_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
                tts.ATTR_OPTIONS: {"tld": "co.uk"},
            },
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.google_en_com",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
                tts.ATTR_OPTIONS: {"tld": "co.uk"},
            },
        ),
    ],
    indirect=["setup"],
)
async def test_service_say_en_couk(
    hass: HomeAssistant,
    mock_gtts: MagicMock,
    hass_client: ClientSessionGenerator,
    calls: list[ServiceCall],
    setup: str,
    tts_service: str,
    service_data: dict[str, Any],
) -> None:
    """Test service call say in co.uk tld accent."""
    await hass.services.async_call(
        tts.DOMAIN,
        tts_service,
        service_data,
        blocking=True,
    )

    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.OK
    )
    assert len(mock_gtts.mock_calls) == 2

    assert mock_gtts.mock_calls[0][2] == {
        "text": "There is a person at the front door.",
        "lang": "en",
        "tld": "co.uk",
    }


@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data"),
    [
        (
            "mock_setup",
            "google_translate_say",
            {
                ATTR_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
            },
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.google_en_com",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
            },
        ),
    ],
    indirect=["setup"],
)
async def test_service_say_error(
    hass: HomeAssistant,
    mock_gtts: MagicMock,
    hass_client: ClientSessionGenerator,
    calls: list[ServiceCall],
    setup: str,
    tts_service: str,
    service_data: dict[str, Any],
) -> None:
    """Test service call say with http response 400."""
    mock_gtts.return_value.write_to_fp.side_effect = gTTSError

    await hass.services.async_call(
        tts.DOMAIN,
        tts_service,
        service_data,
        blocking=True,
    )

    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.NOT_FOUND
    )
    assert len(mock_gtts.mock_calls) == 2
