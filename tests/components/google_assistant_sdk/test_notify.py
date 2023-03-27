"""Tests for the Google Assistant notify."""
from unittest.mock import call, patch

import pytest

from homeassistant.components import notify
from homeassistant.components.google_assistant_sdk import DOMAIN
from homeassistant.components.google_assistant_sdk.const import SUPPORTED_LANGUAGE_CODES
from homeassistant.components.google_assistant_sdk.notify import broadcast_commands
from homeassistant.core import HomeAssistant

from .conftest import ComponentSetup, ExpectedCredentials


@pytest.mark.parametrize(
    ("language_code", "message", "expected_command"),
    [
        ("en-US", "Dinner is served", "broadcast Dinner is served"),
        ("es-ES", "La cena está en la mesa", "Anuncia La cena está en la mesa"),
        ("ko-KR", "저녁 식사가 준비됐어요", "저녁 식사가 준비됐어요 라고 방송해 줘"),
        ("ja-JP", "晩ご飯できたよ", "晩ご飯できたよとブロードキャストして"),
    ],
    ids=["english", "spanish", "korean", "japanese"],
)
async def test_broadcast_no_targets(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    language_code: str,
    message: str,
    expected_command: str,
) -> None:
    """Test broadcast to all."""
    await setup_integration()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    entry.options = {"language_code": language_code}

    with patch(
        "homeassistant.components.google_assistant_sdk.helpers.TextAssistant"
    ) as mock_text_assistant:
        await hass.services.async_call(
            notify.DOMAIN,
            DOMAIN,
            {notify.ATTR_MESSAGE: message},
        )
        await hass.async_block_till_done()
    mock_text_assistant.assert_called_once_with(
        ExpectedCredentials(), language_code, audio_out=False
    )
    mock_text_assistant.assert_has_calls([call().__enter__().assist(expected_command)])


@pytest.mark.parametrize(
    ("language_code", "message", "target", "expected_command"),
    [
        (
            "en-US",
            "it's time for homework",
            "living room",
            "broadcast to living room it's time for homework",
        ),
        (
            "es-ES",
            "Es hora de hacer los deberes",
            "el salón",
            "Anuncia en el salón Es hora de hacer los deberes",
        ),
        ("ko-KR", "숙제할 시간이야", "거실", "숙제할 시간이야 라고 거실에 방송해 줘"),
        ("ja-JP", "宿題の時間だよ", "リビング", "宿題の時間だよとリビングにブロードキャストして"),
    ],
    ids=["english", "spanish", "korean", "japanese"],
)
async def test_broadcast_one_target(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    language_code: str,
    message: str,
    target: str,
    expected_command: str,
) -> None:
    """Test broadcast to one target."""
    await setup_integration()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    entry.options = {"language_code": language_code}

    with patch(
        "homeassistant.components.google_assistant_sdk.helpers.TextAssistant.assist",
        return_value=("text_response", None, b""),
    ) as mock_assist_call:
        await hass.services.async_call(
            notify.DOMAIN,
            DOMAIN,
            {notify.ATTR_MESSAGE: message, notify.ATTR_TARGET: [target]},
        )
        await hass.async_block_till_done()
    mock_assist_call.assert_called_once_with(expected_command)


async def test_broadcast_two_targets(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test broadcast to two targets."""
    await setup_integration()

    message = "time for dinner"
    target1 = "basement"
    target2 = "master bedroom"
    expected_command1 = "broadcast to basement time for dinner"
    expected_command2 = "broadcast to master bedroom time for dinner"
    with patch(
        "homeassistant.components.google_assistant_sdk.helpers.TextAssistant.assist",
        return_value=("text_response", None, b""),
    ) as mock_assist_call:
        await hass.services.async_call(
            notify.DOMAIN,
            DOMAIN,
            {notify.ATTR_MESSAGE: message, notify.ATTR_TARGET: [target1, target2]},
        )
        await hass.async_block_till_done()
    mock_assist_call.assert_has_calls(
        [call(expected_command1), call(expected_command2)]
    )


async def test_broadcast_empty_message(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test broadcast empty message."""
    await setup_integration()

    with patch(
        "homeassistant.components.google_assistant_sdk.helpers.TextAssistant.assist",
        return_value=("text_response", None, b""),
    ) as mock_assist_call:
        await hass.services.async_call(
            notify.DOMAIN,
            DOMAIN,
            {notify.ATTR_MESSAGE: ""},
        )
        await hass.async_block_till_done()
    mock_assist_call.assert_not_called()


def test_broadcast_language_mapping(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test all supported languages have a mapped broadcast command."""
    for language_code in SUPPORTED_LANGUAGE_CODES:
        cmds = broadcast_commands(language_code)
        assert cmds
        assert len(cmds) == 2
        assert cmds[0]
        assert "{0}" in cmds[0]
        assert "{1}" not in cmds[0]
        assert cmds[1]
        assert "{0}" in cmds[1]
        assert "{1}" in cmds[1]
