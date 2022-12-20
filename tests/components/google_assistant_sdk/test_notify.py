"""Tests for the Google Assistant notify."""
from unittest.mock import call, patch

from homeassistant.components import notify
from homeassistant.components.google_assistant_sdk import DOMAIN
from homeassistant.components.google_assistant_sdk.const import SUPPORTED_LANGUAGE_CODES
from homeassistant.components.google_assistant_sdk.notify import broadcast_commands
from homeassistant.core import HomeAssistant

from .conftest import ComponentSetup, ExpectedCredentials


async def test_broadcast_no_targets(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test broadcast to all."""
    await setup_integration()

    message = "time for dinner"
    expected_command = "broadcast time for dinner"
    with patch(
        "homeassistant.components.google_assistant_sdk.helpers.TextAssistant"
    ) as mock_text_assistant:
        await hass.services.async_call(
            notify.DOMAIN,
            DOMAIN,
            {notify.ATTR_MESSAGE: message},
        )
        await hass.async_block_till_done()
    mock_text_assistant.assert_called_once_with(ExpectedCredentials(), "en-US")
    mock_text_assistant.assert_has_calls([call().__enter__().assist(expected_command)])


async def test_broadcast_one_target(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test broadcast to one target."""
    await setup_integration()

    message = "time for dinner"
    target = "basement"
    expected_command = "broadcast to basement time for dinner"
    with patch(
        "homeassistant.components.google_assistant_sdk.helpers.TextAssistant.assist"
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
        "homeassistant.components.google_assistant_sdk.helpers.TextAssistant.assist"
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
        "homeassistant.components.google_assistant_sdk.helpers.TextAssistant.assist"
    ) as mock_assist_call:
        await hass.services.async_call(
            notify.DOMAIN,
            DOMAIN,
            {notify.ATTR_MESSAGE: ""},
        )
        await hass.async_block_till_done()
    mock_assist_call.assert_not_called()


async def test_broadcast_spanish(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test broadcast in Spanish."""
    await setup_integration()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    entry.options = {"language_code": "es-ES"}

    message = "comida"
    expected_command = "Anuncia comida"
    with patch(
        "homeassistant.components.google_assistant_sdk.helpers.TextAssistant"
    ) as mock_text_assistant:
        await hass.services.async_call(
            notify.DOMAIN,
            DOMAIN,
            {notify.ATTR_MESSAGE: message},
        )
        await hass.async_block_till_done()
    mock_text_assistant.assert_called_once_with(ExpectedCredentials(), "es-ES")
    mock_text_assistant.assert_has_calls([call().__enter__().assist(expected_command)])


def test_broadcast_language_mapping(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test all supported languages have a mapped broadcast command."""
    for language_code in SUPPORTED_LANGUAGE_CODES:
        cmds = broadcast_commands(language_code)
        assert cmds
        assert len(cmds) == 2
        assert cmds[0]
        assert cmds[1]
