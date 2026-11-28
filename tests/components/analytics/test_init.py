"""The tests for the analytics ."""

from datetime import timedelta
from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockUser, async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import WebSocketGenerator
from syrupy.assertion import SnapshotAssertion

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

from .conftest import MOCK_SNAPSHOT_PAYLOAD

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
    [
        ("analytics", {}),
        ("analytics/preferences", {"preferences": {"base": True}}),
        ("analytics/preview", {}),
    ],
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


@pytest.mark.parametrize(
    ("preferences", "uuid"),
    [
        pytest.param({}, "abcdefg", id="no_preferences"),
        pytest.param({"base": False, "usage": True}, "abcdefg", id="base_off"),
        pytest.param({"base": True}, "abcdefg", id="base"),
        pytest.param({"base": True}, None, id="base_without_uuid"),
        pytest.param({"base": True, "usage": True}, "abcdefg", id="usage"),
        pytest.param({"base": True, "statistics": True}, "abcdefg", id="statistics"),
        pytest.param(
            {"base": True, "usage": True, "statistics": True}, "abcdefg", id="all"
        ),
    ],
)
@pytest.mark.usefixtures("mock_hass_config")
async def test_websocket_preview(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
    snapshot: SnapshotAssertion,
    preferences: dict[str, bool],
    uuid: str | None,
) -> None:
    """Test previewing the analytics payload without sending or storing it."""
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "key": STORAGE_KEY,
        "data": {"onboarded": True, "preferences": preferences, "uuid": uuid},
    }

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    ws_client = await hass_ws_client(hass)
    with (
        patch("homeassistant.components.analytics.analytics.HA_VERSION", MOCK_VERSION),
        patch(
            "homeassistant.components.analytics.analytics.async_get_system_info",
            return_value={"installation_type": "Home Assistant Tests"},
        ),
    ):
        await ws_client.send_json_auto_id({"type": "analytics/preview"})
        response = await ws_client.receive_json()

    assert response["success"]
    assert response["result"] == snapshot
    assert len(aioclient_mock.mock_calls) == 0
    assert hass_storage[STORAGE_KEY]["data"]["uuid"] == uuid


@pytest.mark.parametrize(
    ("preferences", "labs_features", "snapshot_payload", "expected"),
    [
        pytest.param(
            {"snapshots": True},
            [{"domain": DOMAIN, "preview_feature": LABS_SNAPSHOT_FEATURE}],
            MOCK_SNAPSHOT_PAYLOAD,
            MOCK_SNAPSHOT_PAYLOAD,
            id="enabled",
        ),
        pytest.param(
            {"snapshots": True},
            [{"domain": DOMAIN, "preview_feature": LABS_SNAPSHOT_FEATURE}],
            {},
            None,
            id="nothing_to_send",
        ),
        pytest.param(
            {"snapshots": False},
            [{"domain": DOMAIN, "preview_feature": LABS_SNAPSHOT_FEATURE}],
            MOCK_SNAPSHOT_PAYLOAD,
            None,
            id="preference_off",
        ),
        pytest.param(
            {"snapshots": True},
            [],
            MOCK_SNAPSHOT_PAYLOAD,
            None,
            id="labs_feature_off",
        ),
    ],
)
async def test_websocket_preview_snapshot(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
    preferences: dict[str, bool],
    labs_features: list[dict[str, str]],
    snapshot_payload: dict[str, Any],
    expected: dict[str, Any] | None,
) -> None:
    """Test previewing the snapshot payload without sending it."""
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "key": STORAGE_KEY,
        "data": {"onboarded": True, "preferences": preferences, "uuid": None},
    }
    hass_storage["core.labs"] = {
        "version": 1,
        "key": "core.labs",
        "data": {"preview_feature_status": labs_features},
    }

    assert await async_setup_component(hass, "labs", {})
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    ws_client = await hass_ws_client(hass)
    with patch(
        "homeassistant.components.analytics.analytics._async_snapshot_payload",
        return_value=snapshot_payload,
    ):
        await ws_client.send_json_auto_id({"type": "analytics/preview"})
        response = await ws_client.receive_json()

    assert response["success"]
    assert response["result"] == {"analytics": None, "snapshot": expected}
    assert len(aioclient_mock.mock_calls) == 0


async def test_websocket_preview_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: MockUser,
) -> None:
    """Test previewing the payloads is rejected for non-admin users."""
    hass_admin_user.groups = []
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json_auto_id({"type": "analytics/preview"})
    response = await ws_client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "unauthorized"
