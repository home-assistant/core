"""Tests for the Google Assistant notify."""
from unittest.mock import call, patch

from homeassistant.components import google_assistant as ga, notify
from homeassistant.components.google_assistant import GOOGLE_ASSISTANT_SCHEMA
from homeassistant.setup import async_setup_component

from .test_http import DUMMY_CONFIG


async def setup_notify(hass):
    """Test setup."""
    await async_setup_component(hass, ga.DOMAIN, {ga.DOMAIN: DUMMY_CONFIG})
    await hass.async_block_till_done()
    assert hass.services.has_service(notify.DOMAIN, ga.DOMAIN)


async def test_broadcast_no_targets(hass):
    """Test broadcast to all."""
    await setup_notify(hass)

    message = "time for dinner"
    expected_command = "broadcast time for dinner"
    with patch(
        "homeassistant.components.google_assistant.helpers.TextAssistant.assist"
    ) as mock_assist_call:
        await hass.services.async_call(
            notify.DOMAIN, ga.DOMAIN, {notify.ATTR_MESSAGE: message}
        )
        await hass.async_block_till_done()
    mock_assist_call.assert_called_once_with(expected_command)


async def test_broadcast_one_target(hass):
    """Test broadcast to one target."""
    await setup_notify(hass)

    message = "time for dinner"
    target = "basement"
    expected_command = "broadcast to basement time for dinner"
    with patch(
        "homeassistant.components.google_assistant.helpers.TextAssistant.assist"
    ) as mock_assist_call:
        await hass.services.async_call(
            notify.DOMAIN,
            ga.DOMAIN,
            {notify.ATTR_MESSAGE: message, notify.ATTR_TARGET: [target]},
        )
        await hass.async_block_till_done()
    mock_assist_call.assert_called_once_with(expected_command)


async def test_broadcast_two_targets(hass):
    """Test broadcast to two targets."""
    await setup_notify(hass)

    message = "time for dinner"
    target1 = "basement"
    target2 = "master bedroom"
    expected_command1 = "broadcast to basement time for dinner"
    expected_command2 = "broadcast to master bedroom time for dinner"
    with patch(
        "homeassistant.components.google_assistant.helpers.TextAssistant.assist"
    ) as mock_assist_call:
        await hass.services.async_call(
            notify.DOMAIN,
            ga.DOMAIN,
            {notify.ATTR_MESSAGE: message, notify.ATTR_TARGET: [target1, target2]},
        )
        await hass.async_block_till_done()
    mock_assist_call.assert_has_calls(
        [call(expected_command1), call(expected_command2)]
    )


async def test_broadcast_empty_message(hass):
    """Test broadcast empty message."""
    await setup_notify(hass)

    message = ""
    with patch(
        "homeassistant.components.google_assistant.helpers.TextAssistant.assist"
    ) as mock_assist_call:
        await hass.services.async_call(
            notify.DOMAIN,
            ga.DOMAIN,
            {notify.ATTR_MESSAGE: message},
        )
        await hass.async_block_till_done()
    mock_assist_call.assert_not_called()


async def test_no_broadcast_service(hass):
    """Test no broadcast service when there is no service_account in config."""
    await async_setup_component(
        hass, ga.DOMAIN, {ga.DOMAIN: GOOGLE_ASSISTANT_SCHEMA({"project_id": "1234"})}
    )
    await hass.async_block_till_done()
    assert not hass.services.has_service(notify.DOMAIN, ga.DOMAIN)
