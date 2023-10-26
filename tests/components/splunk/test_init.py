"""Test the Aussie Broadband init."""
from asyncio import TimeoutError
from http import HTTPStatus
from unittest.mock import patch

from aiohttp import ClientConnectionError, ClientResponseError
from hass_splunk import SplunkPayloadError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import HomeAssistant, State

from . import RETURN_BADAUTH, RETURN_SUCCESS, URL, setup_platform

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_unload(hass: HomeAssistant) -> None:
    """Test unload."""
    entry = await setup_platform(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_auth_failure(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test init with an authentication failure."""

    aioclient_mock.post(
        URL,
        text=RETURN_BADAUTH,
        status=HTTPStatus.FORBIDDEN,
    )

    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_net_failure(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test init with a network failure."""
    aioclient_mock.post(
        URL,
        side_effect=ClientConnectionError,
    )

    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_event(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Test event."""
    aioclient_mock.post(URL, text=RETURN_SUCCESS)

    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert aioclient_mock.call_count == 1

    # Test event
    hass.bus.async_fire(
        EVENT_STATE_CHANGED,
        {
            "entity_id": "splunk.test",
            "old_state": None,
            "new_state": State("splunk.test", "Success"),
        },
    )
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 2


async def test_event_failures(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test event."""
    aioclient_mock.post(
        URL,
        text=RETURN_SUCCESS,
    )

    await setup_platform(hass)
    # Other Failure
    with patch(
        "hass_splunk.hass_splunk.queue",
        side_effect=SplunkPayloadError(
            message="Bad Request", code=5, status=HTTPStatus.BAD_REQUEST
        ),
    ):
        # Test event
        hass.bus.async_fire(
            EVENT_STATE_CHANGED,
            {
                "entity_id": "splunk.test",
                "old_state": None,
                "new_state": State("splunk.test", "Success"),
            },
        )
        await hass.async_block_till_done()

    # Client Connection Error
    with patch(
        "hass_splunk.hass_splunk.queue",
        side_effect=ClientConnectionError(),
    ):
        # Test event
        hass.bus.async_fire(
            EVENT_STATE_CHANGED,
            {
                "entity_id": "splunk.test",
                "old_state": None,
                "new_state": State("splunk.test", "Success"),
            },
        )
        await hass.async_block_till_done()

    # Timeout Error
    with patch(
        "hass_splunk.hass_splunk.queue",
        side_effect=TimeoutError(),
    ):
        # Test event
        hass.bus.async_fire(
            EVENT_STATE_CHANGED,
            {
                "entity_id": "splunk.test",
                "old_state": None,
                "new_state": State("splunk.test", "Success"),
            },
        )
        await hass.async_block_till_done()

    # Response Error
    with patch(
        "hass_splunk.hass_splunk.queue",
        side_effect=ClientResponseError(None, None, status=HTTPStatus.BAD_REQUEST),
    ):
        # Test event
        hass.bus.async_fire(
            EVENT_STATE_CHANGED,
            {
                "entity_id": "splunk.test",
                "old_state": None,
                "new_state": State("splunk.test", "Success"),
            },
        )
        await hass.async_block_till_done()
