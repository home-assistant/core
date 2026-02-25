"""The tests for the Pico TTS speech platform."""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, mock_open, patch

import pytest

from homeassistant.components import tts
from homeassistant.components.media_player import ATTR_MEDIA_CONTENT_ID
from homeassistant.components.picotts.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.core_config import async_process_ha_core_config

from tests.common import MockConfigEntry
from tests.components.tts.common import retrieve_media
from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
def tts_mutagen_mock_fixture_autouse(tts_mutagen_mock: MagicMock) -> None:
    """Mock writing tags."""


@pytest.fixture(autouse=True)
def mock_tts_cache_dir_autouse(mock_tts_cache_dir: Path) -> None:
    """Mock the TTS cache dir with empty dir."""


@pytest.fixture(autouse=True)
async def setup_internal_url(hass: HomeAssistant) -> None:
    """Set up internal url."""
    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:8123"}
    )


@pytest.fixture(name="setup")
async def setup_fixture(
    hass: HomeAssistant,
    config: dict[str, Any],
    request: pytest.FixtureRequest,
) -> None:
    """Set up the test environment."""
    if request.param == "mock_config_entry_setup":
        await mock_config_entry_setup(hass, config)
    else:
        raise RuntimeError("Invalid setup fixture")

    await hass.async_block_till_done()


@pytest.fixture(name="config")
def config_fixture() -> dict[str, Any]:
    """Return config."""
    return {}


async def mock_config_entry_setup(hass: HomeAssistant, config: dict[str, Any]) -> None:
    """Mock config entry setup."""
    default_config = {tts.CONF_LANG: "en-US"}
    config_entry = MockConfigEntry(domain=DOMAIN, data=default_config | config)
    config_entry.add_to_hass(hass)

    with patch("shutil.which", return_value="/usr/local/bin/pico2wave"):
        assert await hass.config_entries.async_setup(config_entry.entry_id)


@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data"),
    [
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.pico_tts_en_us",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
            },
        ),
    ],
    indirect=["setup"],
)
async def test_tts_service(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    service_calls: list[ServiceCall],
    setup: str,
    tts_service: str,
    service_data: dict[str, Any],
) -> None:
    """Test tts service."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    with (
        patch(
            "homeassistant.components.picotts.tts.subprocess.run",
            return_value=mock_result,
        ),
        patch("builtins.open", mock_open(read_data=b"fake-wav-data")),
        patch("homeassistant.components.picotts.tts.os.remove"),
    ):
        await hass.services.async_call(
            tts.DOMAIN,
            tts_service,
            service_data,
            blocking=True,
        )

        assert len(service_calls) == 2
        assert (
            await retrieve_media(
                hass, hass_client, service_calls[1].data[ATTR_MEDIA_CONTENT_ID]
            )
            == HTTPStatus.OK
        )


@pytest.mark.parametrize("config", [{tts.CONF_LANG: "de-DE"}])
@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data"),
    [
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.pico_tts_de_de",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
            },
        ),
    ],
    indirect=["setup"],
)
async def test_service_say_german_config(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    service_calls: list[ServiceCall],
    setup: str,
    tts_service: str,
    service_data: dict[str, Any],
) -> None:
    """Test service call say with german code in the config."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    with (
        patch(
            "homeassistant.components.picotts.tts.subprocess.run",
            return_value=mock_result,
        ),
        patch("builtins.open", mock_open(read_data=b"fake-wav-data")),
        patch("homeassistant.components.picotts.tts.os.remove"),
    ):
        await hass.services.async_call(
            tts.DOMAIN,
            tts_service,
            service_data,
            blocking=True,
        )

        assert len(service_calls) == 2
        # assert (
        #     await retrieve_media(
        #         hass, hass_client, service_calls[1].data[ATTR_MEDIA_CONTENT_ID]
        #     )
        #     == HTTPStatus.OK
        # )


@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data"),
    [
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.pico_tts_en_us",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
                tts.ATTR_LANGUAGE: "de-DE",
            },
        ),
    ],
    indirect=["setup"],
)
async def test_service_say_german_service(
    hass: HomeAssistant,
    # mock_gtts: MagicMock,
    hass_client: ClientSessionGenerator,
    service_calls: list[ServiceCall],
    setup: str,
    tts_service: str,
    service_data: dict[str, Any],
) -> None:
    """Test service call say with german code in the service."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    with (
        patch(
            "homeassistant.components.picotts.tts.subprocess.run",
            return_value=mock_result,
        ),
        patch("builtins.open", mock_open(read_data=b"fake-wav-data")),
        patch("homeassistant.components.picotts.tts.os.remove"),
    ):
        await hass.services.async_call(
            tts.DOMAIN,
            tts_service,
            service_data,
            blocking=True,
        )

        assert len(service_calls) == 2
        # assert (
        #     await retrieve_media(
        #         hass, hass_client, service_calls[1].data[ATTR_MEDIA_CONTENT_ID]
        #     )
        #     == HTTPStatus.OK
        # )


@pytest.mark.parametrize("config", [{tts.CONF_LANG: "en-GB"}])
@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data"),
    [
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.pico_tts_en_gb",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
            },
        ),
    ],
    indirect=["setup"],
)
async def test_service_say_en_gb_config(
    hass: HomeAssistant,
    # mock_gtts: MagicMock,
    hass_client: ClientSessionGenerator,
    service_calls: list[ServiceCall],
    setup: str,
    tts_service: str,
    service_data: dict[str, Any],
) -> None:
    """Test service call say with en-gb code in the config."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    with (
        patch(
            "homeassistant.components.picotts.tts.subprocess.run",
            return_value=mock_result,
        ),
        patch("builtins.open", mock_open(read_data=b"fake-wav-data")),
        patch("homeassistant.components.picotts.tts.os.remove"),
    ):
        await hass.services.async_call(
            tts.DOMAIN,
            tts_service,
            service_data,
            blocking=True,
        )

        assert len(service_calls) == 2
        # assert (
        #     await retrieve_media(
        #         hass, hass_client, service_calls[1].data[ATTR_MEDIA_CONTENT_ID]
        #     )
        #     == HTTPStatus.OK
        # )


@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data"),
    [
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.pico_tts_en_us",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
                tts.ATTR_LANGUAGE: "en-GB",
            },
        ),
    ],
    indirect=["setup"],
)
async def test_service_say_en_gb_service(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    service_calls: list[ServiceCall],
    setup: str,
    tts_service: str,
    service_data: dict[str, Any],
) -> None:
    """Test service call say with en-gb code in the config."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    with (
        patch(
            "homeassistant.components.picotts.tts.subprocess.run",
            return_value=mock_result,
        ),
        patch("builtins.open", mock_open(read_data=b"fake-wav-data")),
        patch("homeassistant.components.picotts.tts.os.remove"),
    ):
        await hass.services.async_call(
            tts.DOMAIN,
            tts_service,
            service_data,
            blocking=True,
        )

        assert len(service_calls) == 2
        # assert (
        #     await retrieve_media(
        #         hass, hass_client, service_calls[1].data[ATTR_MEDIA_CONTENT_ID]
        #     )
        #     == HTTPStatus.OK
        # )
