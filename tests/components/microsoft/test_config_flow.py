"""Test the Microsoft Text-to-Speech config flow."""

from http import HTTPStatus
from typing import Any
from unittest.mock import DEFAULT, AsyncMock, MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from requests.exceptions import ConnectionError as RequestsConnectionError

from homeassistant.components.microsoft.const import (
    CONF_CONTOUR,
    CONF_GENDER,
    CONF_PITCH,
    CONF_RATE,
    CONF_VOLUME,
    DOMAIN,
)
from homeassistant.components.tts import CONF_LANG, async_create_stream
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_PLATFORM, CONF_REGION, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import http_error

ENTITY_ID = "tts.microsoft_text_to_speech"
MESSAGE = "There is a person at the front door."

USER_INPUT = {
    CONF_API_KEY: "test-api-key",
    CONF_REGION: "westeurope",
    CONF_LANG: "de-de",
    CONF_GENDER: "male",
    CONF_TYPE: "ConradNeural",
}

DEFAULT_OPTIONS = {
    CONF_RATE: 0,
    CONF_VOLUME: 0,
    CONF_PITCH: "default",
    CONF_CONTOUR: "",
}

OPTIONS = {
    CONF_RATE: 20,
    CONF_VOLUME: -20,
    CONF_PITCH: "low",
    CONF_CONTOUR: "(0%,+20Hz)",
}

OPTIONS_SPEAK_KWARGS = {
    "language": "en-gb",
    "gender": "Female",
    "voiceType": "AbbiNeural",
    "output": "audio-24khz-96kbitrate-mono-mp3",
    "rate": "20%",
    "volume": "-20%",
    "pitch": "low",
    "contour": "(0%,+20Hz)",
    "text": MESSAGE,
}


ERRORS = [
    pytest.param(
        http_error(HTTPStatus.UNAUTHORIZED), "invalid_api_key", id="invalid_api_key"
    ),
    pytest.param(
        http_error(HTTPStatus.INTERNAL_SERVER_ERROR),
        "cannot_connect",
        id="http_error",
    ),
    pytest.param(RequestsConnectionError, "cannot_connect", id="cannot_connect"),
    pytest.param(ValueError, "unknown", id="unknown"),
]


async def test_user_flow(
    hass: HomeAssistant, mock_tts_translator: MagicMock, mock_setup_entry: AsyncMock
) -> None:
    """Test the user flow creates an entry with default prosody options."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Microsoft Text-to-Speech"
    assert result["data"] == USER_INPUT
    assert result["options"] == DEFAULT_OPTIONS
    mock_tts_translator.assert_called_once_with("test-api-key", "westeurope")
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(("side_effect", "error"), ERRORS)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_tts_translator: MagicMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test the user flow shows an error and recovers from it."""
    mock_tts_translator.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_tts_translator.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry", "mock_tts_translator")
async def test_user_flow_defaults(hass: HomeAssistant) -> None:
    """Test the user flow uses the default voice if none is entered."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "test-api-key"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_API_KEY: "test-api-key",
        CONF_REGION: "eastus",
        CONF_LANG: "en-us",
        CONF_GENDER: "female",
        CONF_TYPE: "JennyNeural",
    }


@pytest.mark.usefixtures("mock_setup_entry", "mock_tts_translator")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the user flow aborts if the API key is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "test-api-key", CONF_REGION: "eastus"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import(hass: HomeAssistant, mock_tts_translator: MagicMock) -> None:
    """Test importing the YAML configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_PLATFORM: DOMAIN, **USER_INPUT, CONF_GENDER: "Male", **OPTIONS},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Microsoft Text-to-Speech"
    assert result["data"] == USER_INPUT
    assert result["options"] == OPTIONS
    mock_tts_translator.assert_called_once_with("test-api-key", "westeurope")


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(("side_effect", "reason"), ERRORS)
async def test_import_errors(
    hass: HomeAssistant,
    mock_tts_translator: MagicMock,
    side_effect: Exception,
    reason: str,
) -> None:
    """Test the import aborts if the credentials can't be validated."""
    mock_tts_translator.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_PLATFORM: DOMAIN, **USER_INPUT, **OPTIONS},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.usefixtures("mock_setup_entry", "mock_tts_translator")
async def test_import_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the import aborts if the API key is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_PLATFORM: DOMAIN, **USER_INPUT, **OPTIONS},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_configured_during_validation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tts_translator: MagicMock,
) -> None:
    """Test the import aborts if the API key gets configured during validation."""

    def configure_meanwhile(api_key: str, region: str) -> object:
        mock_config_entry.add_to_hass(hass)
        return DEFAULT

    mock_tts_translator.side_effect = configure_meanwhile

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_PLATFORM: DOMAIN, **USER_INPUT, **OPTIONS},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN) == [mock_config_entry]


@pytest.mark.parametrize(
    ("user_input", "expected_options", "expected_speak_kwargs"),
    [
        pytest.param(OPTIONS, OPTIONS, OPTIONS_SPEAK_KWARGS, id="all_options"),
        pytest.param(
            {CONF_RATE: 20, CONF_VOLUME: -20},
            {**OPTIONS, CONF_PITCH: "default", CONF_CONTOUR: ""},
            OPTIONS_SPEAK_KWARGS | {"pitch": "default", "contour": ""},
            id="cleared_pitch_and_contour",
        ),
    ],
)
async def test_options_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tts_translator: MagicMock,
    user_input: dict[str, Any],
    expected_options: dict[str, Any],
    expected_speak_kwargs: dict[str, Any],
) -> None:
    """Test the options flow updates the prosody options of the entity."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == expected_options

    stream = async_create_stream(hass, ENTITY_ID)
    stream.async_set_message(MESSAGE)
    assert b"".join([chunk async for chunk in stream.async_stream_result()]) == b"audio"
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_tts_translator.return_value.speak.assert_called_once_with(
        **expected_speak_kwargs
    )
