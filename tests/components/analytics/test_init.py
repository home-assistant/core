"""The tests for the analytics ."""

from datetime import timedelta
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.analytics import LABS_SNAPSHOT_FEATURE
from homeassistant.components.analytics.const import (
    BASIC_ENDPOINT_URL,
    DOMAIN,
    SNAPSHOT_DEFAULT_URL,
    SNAPSHOT_URL_PATH,
    STORAGE_KEY,
)
from homeassistant.components.labs import async_update_preview_feature
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import WebSocketGenerator

MOCK_VERSION = "1970.1.0"

SNAPSHOT_ENDPOINT_URL = SNAPSHOT_DEFAULT_URL + SNAPSHOT_URL_PATH


async def test_setup(hass: HomeAssistant) -> None:
    """Test setup of the integration."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    assert DOMAIN in hass.data


@pytest.mark.usefixtures("mock_snapshot_payload")
async def test_labs_feature_toggle(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that snapshots can be toggled via labs feature."""
    aioclient_mock.post(SNAPSHOT_ENDPOINT_URL, status=200, json={})

    assert await async_setup_component(hass, "labs", {})
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=25))
    await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 0

    await async_update_preview_feature(hass, DOMAIN, LABS_SNAPSHOT_FEATURE, True)

    assert hass_storage[STORAGE_KEY]["data"]["preferences"]["snapshots"] is True

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=25))
    await hass.async_block_till_done()

    assert any(
        str(call[1]) == SNAPSHOT_ENDPOINT_URL for call in aioclient_mock.mock_calls
    )

    aioclient_mock.clear_requests()

    await async_update_preview_feature(hass, DOMAIN, LABS_SNAPSHOT_FEATURE, False)

    assert hass_storage[STORAGE_KEY]["data"]["preferences"]["snapshots"] is False

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=25))
    await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 0


@pytest.mark.usefixtures("supervisor_client")
async def test_websocket(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test WebSocket commands."""
    aioclient_mock.post(BASIC_ENDPOINT_URL, status=200)
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json_auto_id({"type": "analytics"})

    response = await ws_client.receive_json()

    assert response["success"]

    with patch("homeassistant.components.analytics.analytics.HA_VERSION", MOCK_VERSION):
        await ws_client.send_json_auto_id(
            {"type": "analytics/preferences", "preferences": {"base": True}}
        )
        response = await ws_client.receive_json()
    assert response["result"]["preferences"]["base"]

    await ws_client.send_json_auto_id({"type": "analytics"})
    response = await ws_client.receive_json()
    assert response["result"]["preferences"]["base"]
