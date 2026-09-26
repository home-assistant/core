"""Config-entry lifecycle: unloading is not the user stopping following.

The distinction matters more here than in most integrations, because the whole point of the
feature is that it keeps working while the phone's app is not running. A reload, a restart or
Home Assistant stopping must leave every Follow relationship exactly as it was; only removing the
registration ends them.
"""

import asyncio
from http import HTTPStatus
from typing import Any

from homeassistant.components.mobile_app.remote_media.manager import async_get_manager
from homeassistant.components.mobile_app.remote_media.store import async_save_session
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import WEBHOOK_ID, session, stored_sessions
from .const import (
    ENTITY_ID,
    GENERATION,
    PLAYING_ATTRIBUTES,
    PUSH_TOKEN,
    PUSH_URL,
    SEQUENCE,
    SESSION_ID,
)

from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse


def _ends(aioclient_mock: AiohttpClientMocker) -> list:
    """Every `end` the relay was asked to deliver."""
    return [
        call
        for call in aioclient_mock.mock_calls
        if call[2]["now_playing"]["event"] == "end"
    ]


async def _follow(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Start following, stored and watched."""
    hass.states.async_set(ENTITY_ID, "playing", PLAYING_ATTRIBUTES)
    await hass.async_block_till_done()
    following = session()
    async_save_session(hass, WEBHOOK_ID, following)
    async_get_manager(hass).async_add(WEBHOOK_ID, following, entry, reconcile=False)


async def test_unloading_keeps_the_relationship_and_sends_nothing(
    hass: HomeAssistant, push_entry: ConfigEntry, aioclient_mock: AiohttpClientMocker
) -> None:
    """A reload or a shutdown is not Stop Following."""
    aioclient_mock.post(PUSH_URL, status=HTTPStatus.CREATED, json={})
    await _follow(hass, push_entry)
    manager = async_get_manager(hass)
    assert manager.async_get(WEBHOOK_ID, SESSION_ID) is not None

    assert await hass.config_entries.async_unload(push_entry.entry_id)
    await hass.async_block_till_done()

    # The relationship, its token and its sticky state are all still there.
    assert SESSION_ID in stored_sessions(hass, WEBHOOK_ID)
    assert stored_sessions(hass, WEBHOOK_ID)[SESSION_ID]["push_token"] == PUSH_TOKEN
    assert stored_sessions(hass, WEBHOOK_ID)[SESSION_ID]["generation"] == GENERATION
    assert (
        stored_sessions(hass, WEBHOOK_ID)[SESSION_ID]["generation_sequence"] == SEQUENCE
    )
    # Nothing was told the card, and nothing is being watched.
    assert not _ends(aioclient_mock)
    assert manager.async_get(WEBHOOK_ID, SESSION_ID) is None
    assert ENTITY_ID not in manager.watchers


async def test_setting_up_again_restores_and_reconciles(
    hass: HomeAssistant, push_entry: ConfigEntry, aioclient_mock: AiohttpClientMocker
) -> None:
    """The listener comes back and the card is brought up to date from current state."""
    aioclient_mock.post(PUSH_URL, status=HTTPStatus.CREATED, json={})
    await _follow(hass, push_entry)

    assert await hass.config_entries.async_unload(push_entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(push_entry.entry_id)
    await hass.async_block_till_done()

    manager = async_get_manager(hass)
    publisher = manager.async_get(WEBHOOK_ID, SESSION_ID)
    assert publisher is not None
    assert publisher.session.push_token == PUSH_TOKEN
    assert ENTITY_ID in manager.watchers
    assert not _ends(aioclient_mock)


async def test_a_reload_survives_repeatedly(
    hass: HomeAssistant, push_entry: ConfigEntry, aioclient_mock: AiohttpClientMocker
) -> None:
    """Nothing accumulates: one listener and one publisher, however many reloads."""
    aioclient_mock.post(PUSH_URL, status=HTTPStatus.CREATED, json={})
    await _follow(hass, push_entry)

    for _ in range(3):
        await hass.config_entries.async_reload(push_entry.entry_id)
        await hass.async_block_till_done()

    manager = async_get_manager(hass)
    assert push_entry.state is ConfigEntryState.LOADED
    assert len(stored_sessions(hass, WEBHOOK_ID)) == 1
    assert len(manager.watchers[ENTITY_ID].publishers) == 1
    assert not _ends(aioclient_mock)


async def test_removing_the_registration_ends_everything(
    hass: HomeAssistant, push_entry: ConfigEntry, aioclient_mock: AiohttpClientMocker
) -> None:
    """Removal is permanent, and tells the card best effort."""
    aioclient_mock.post(PUSH_URL, status=HTTPStatus.CREATED, json={})
    await _follow(hass, push_entry)

    assert await hass.config_entries.async_remove(push_entry.entry_id)
    await hass.async_block_till_done()

    manager = async_get_manager(hass)
    assert stored_sessions(hass, WEBHOOK_ID) == {}
    assert manager.async_get(WEBHOOK_ID, SESSION_ID) is None
    assert ENTITY_ID not in manager.watchers
    assert _ends(aioclient_mock)


async def test_a_late_end_completion_does_not_restore_the_session(
    hass: HomeAssistant, push_entry: ConfigEntry, aioclient_mock: AiohttpClientMocker
) -> None:
    """An end response arriving after removal must not recreate persisted state."""
    release = asyncio.Event()

    async def slow_end(
        method: str, url: str, data: dict[str, Any]
    ) -> AiohttpClientMockResponse:
        assert data["now_playing"]["event"] == "end"
        await release.wait()
        return AiohttpClientMockResponse(
            method, url, status=HTTPStatus.CREATED, json={}
        )

    aioclient_mock.post(PUSH_URL, side_effect=slow_end)
    await _follow(hass, push_entry)
    async_get_manager(hass).async_end_session(WEBHOOK_ID, SESSION_ID)
    await asyncio.sleep(0)

    assert stored_sessions(hass, WEBHOOK_ID) == {}
    release.set()
    await hass.async_block_till_done()
    assert stored_sessions(hass, WEBHOOK_ID) == {}


async def test_a_relay_outage_cannot_block_removal(
    hass: HomeAssistant, push_entry: ConfigEntry, aioclient_mock: AiohttpClientMocker
) -> None:
    """Deleting a config entry must never depend on an external service answering."""
    aioclient_mock.post(PUSH_URL, exc=TimeoutError())
    await _follow(hass, push_entry)

    assert await hass.config_entries.async_remove(push_entry.entry_id)
    await hass.async_block_till_done()

    assert stored_sessions(hass, WEBHOOK_ID) == {}
    assert async_get_manager(hass).async_get(WEBHOOK_ID, SESSION_ID) is None
