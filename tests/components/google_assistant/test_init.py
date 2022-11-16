"""The tests for google-assistant init."""
from http import HTTPStatus
from unittest.mock import patch

from homeassistant.components import google_assistant as ga
from homeassistant.core import Context, HomeAssistant
from homeassistant.setup import async_setup_component

from .test_http import DUMMY_CONFIG

from tests.common import MockConfigEntry


async def test_import(hass: HomeAssistant):
    """Test import."""

    await async_setup_component(
        hass,
        ga.DOMAIN,
        {"google_assistant": DUMMY_CONFIG},
    )

    entries = hass.config_entries.async_entries("google_assistant")
    assert len(entries) == 1
    assert entries[0].data[ga.const.CONF_PROJECT_ID] == "1234"


async def test_import_changed(hass: HomeAssistant):
    """Test import with changed project id."""

    old_entry = MockConfigEntry(
        domain=ga.DOMAIN, data={ga.const.CONF_PROJECT_ID: "4321"}, source="import"
    )
    old_entry.add_to_hass(hass)

    await async_setup_component(
        hass,
        ga.DOMAIN,
        {"google_assistant": DUMMY_CONFIG},
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries("google_assistant")
    assert len(entries) == 1
    assert entries[0].data[ga.const.CONF_PROJECT_ID] == "1234"


async def test_request_sync_service(aioclient_mock, hass):
    """Test that it posts to the request_sync url."""
    aioclient_mock.post(
        ga.const.HOMEGRAPH_TOKEN_URL,
        status=HTTPStatus.OK,
        json={"access_token": "1234", "expires_in": 3600},
    )

    aioclient_mock.post(ga.const.REQUEST_SYNC_BASE_URL, status=HTTPStatus.OK)

    await async_setup_component(
        hass,
        "google_assistant",
        {"google_assistant": DUMMY_CONFIG},
    )

    assert aioclient_mock.call_count == 0
    await hass.services.async_call(
        ga.const.DOMAIN,
        ga.const.SERVICE_REQUEST_SYNC,
        blocking=True,
        context=Context(user_id="123"),
    )

    assert aioclient_mock.call_count == 2  # token + request


async def test_send_text_command_service(hass):
    """Test send_text_command calls TextAssistant."""
    await async_setup_component(hass, ga.DOMAIN, {ga.DOMAIN: DUMMY_CONFIG})
    await hass.async_block_till_done()

    command = "turn on home assistant unsupported device"
    with patch(
        "homeassistant.components.google_assistant.helpers.TextAssistant.assist"
    ) as mock_assist_call:
        await hass.services.async_call(
            ga.DOMAIN,
            ga.SERVICE_SEND_TEXT_COMMAND,
            {ga.SERVICE_SEND_TEXT_COMMAND_FIELD_COMMAND: command},
            blocking=True,
        )
    mock_assist_call.assert_called_once_with(command)
