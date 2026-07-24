"""The tests for the analytics ."""

from datetime import timedelta
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.analytics import CONF_SNAPSHOTS_URL, LABS_SNAPSHOT_FEATURE
from homeassistant.components.analytics.const import (
    BASIC_ENDPOINT_URL,
    BASIC_ENDPOINT_URL_DEV,
    DOMAIN,
    SNAPSHOT_DEFAULT_URL,
    SNAPSHOT_URL_PATH,
    STORAGE_KEY,
)
from homeassistant.components.hassio import HassioNotReadyError
from homeassistant.components.labs import async_update_preview_feature
from homeassistant.config_entries import ConfigEntryState
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


async def test_setup_with_snapshots_url(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test setup with snapshots_url in YAML config sends snapshots to that URL."""
    custom_url = "https://custom-snapshot-endpoint.example.com"
    snapshot_endpoint = custom_url + SNAPSHOT_URL_PATH
    aioclient_mock.post(snapshot_endpoint, status=200, json={})

    with patch(
        "homeassistant.components.analytics.analytics._async_snapshot_payload",
        return_value={"mock": {}},
    ):
        assert await async_setup_component(hass, "labs", {})
        assert await async_setup_component(
            hass, DOMAIN, {DOMAIN: {CONF_SNAPSHOTS_URL: custom_url}}
        )
        await hass.async_block_till_done()

        ws_client = await hass_ws_client(hass)
        await ws_client.send_json_auto_id(
            {"type": "analytics/preferences", "preferences": {"snapshots": True}}
        )
        assert (await ws_client.receive_json())["success"]

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=25))
        await hass.async_block_till_done()

    assert any(str(call[1]) == snapshot_endpoint for call in aioclient_mock.mock_calls)


async def test_setup_entry_supervisor_not_ready(hass: HomeAssistant) -> None:
    """Test that HassioNotReadyError raises ConfigEntryNotReady."""
    with (
        patch(
            "homeassistant.components.analytics.analytics.is_hassio",
            return_value=True,
        ),
        patch(
            "homeassistant.components.hassio.get_supervisor_info",
            side_effect=HassioNotReadyError,
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_schedule_starts_and_sends_analytics(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the analytics schedule fires and sends analytics after time travel."""
    aioclient_mock.post(BASIC_ENDPOINT_URL, status=200)
    aioclient_mock.post(BASIC_ENDPOINT_URL_DEV, status=200)

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    ws_client = await hass_ws_client(hass)
    with patch("homeassistant.components.analytics.analytics.HA_VERSION", MOCK_VERSION):
        await ws_client.send_json_auto_id(
            {"type": "analytics/preferences", "preferences": {"base": True}}
        )
        assert (await ws_client.receive_json())["success"]

        assert len(aioclient_mock.mock_calls) == 0

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=901))
        await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 1


@pytest.mark.parametrize(
    ("ws_type", "ws_options"),
    [("analytics", {}), ("analytics/preferences", {"preferences": {"base": True}})],
)
async def test_websocket_not_loaded(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    ws_type: str,
    ws_options: dict[str, Any],
) -> None:
    """Test websocket returns error when analytics entry failed to load."""
    with (
        patch(
            "homeassistant.components.analytics.analytics.is_hassio",
            return_value=True,
        ),
        patch(
            "homeassistant.components.hassio.get_supervisor_info",
            side_effect=HassioNotReadyError,
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json_auto_id({"type": ws_type} | ws_options)
    response = await ws_client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "not_found"


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
