"""Tests for update entities."""
import pytest
import requests_mock

from homeassistant.components.update import (
    DOMAIN as UPDATE_DOMAIN,
    SCAN_INTERVAL as UPDATER_SCAN_INTERVAL,
    SERVICE_INSTALL,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, HomeAssistantError
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import WebSocketGenerator

UPDATE_ENTITY = "update.plex_media_server_plex_server_1"


async def test_plex_update(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    mock_plex_server,
    requests_mock: requests_mock.Mocker,
    empty_payload: str,
    update_check_new: str,
    update_check_new_not_updatable: str,
) -> None:
    """Test Plex update entity."""
    ws_client = await hass_ws_client(hass)

    assert hass.states.get(UPDATE_ENTITY).state == STATE_OFF
    await ws_client.send_json(
        {
            "id": 1,
            "type": "update/release_notes",
            "entity_id": UPDATE_ENTITY,
        }
    )
    result = await ws_client.receive_json()
    assert result["result"] is None

    apply_mock = requests_mock.put("/updater/apply")

    # Failed updates
    requests_mock.get("/updater/status", status_code=500)
    async_fire_time_changed(hass, dt_util.utcnow() + UPDATER_SCAN_INTERVAL)
    await hass.async_block_till_done()

    requests_mock.get("/updater/status", text=empty_payload)
    async_fire_time_changed(hass, dt_util.utcnow() + UPDATER_SCAN_INTERVAL)
    await hass.async_block_till_done()

    # New release (not updatable)
    requests_mock.get("/updater/status", text=update_check_new_not_updatable)
    async_fire_time_changed(hass, dt_util.utcnow() + UPDATER_SCAN_INTERVAL)
    await hass.async_block_till_done()
    assert hass.states.get(UPDATE_ENTITY).state == STATE_ON

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {
                ATTR_ENTITY_ID: UPDATE_ENTITY,
            },
            blocking=True,
        )
    assert not apply_mock.called

    # New release (updatable)
    requests_mock.get("/updater/status", text=update_check_new)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(UPDATE_ENTITY).state == STATE_ON

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            "id": 1,
            "type": "update/release_notes",
            "entity_id": UPDATE_ENTITY,
        }
    )
    result = await ws_client.receive_json()
    assert result["result"] == "* Summary of\n* release notes"

    # Successful upgrade request
    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {
            ATTR_ENTITY_ID: UPDATE_ENTITY,
        },
        blocking=True,
    )
    assert apply_mock.called_once

    # Failed upgrade request
    requests_mock.put("/updater/apply", status_code=500)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {
                ATTR_ENTITY_ID: UPDATE_ENTITY,
            },
            blocking=True,
        )
