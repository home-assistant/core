"""Tests for the Home Assistant Upgrade Check websocket API."""

from typing import Any

import aiohttp
import pytest
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import WebSocketGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.homeassistant_upgrade_check.const import DOMAIN
from homeassistant.components.homeassistant_upgrade_check.feed import POSTS_URL
from homeassistant.components.homeassistant_upgrade_check.mock import (
    MOCK_RUNNING,
    MOCK_TARGET,
)
from homeassistant.components.homeassistant_upgrade_check.release_notes import (
    INDEX_FORMAT,
)
from homeassistant.components.update import (
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    DOMAIN as UPDATE_DOMAIN,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

DIGEST = f"{DOMAIN}/digest"
MOCK_CORE_UPDATE = "update.home_assistant_core_mock"


@pytest.mark.usefixtures("installed_integrations", "setup_integration")
async def test_digest(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    snapshot: SnapshotAssertion,
) -> None:
    """Test the items that affect the installed integrations."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": DIGEST})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == snapshot
    # The parsed releases are kept, like a fetched feed would be.
    assert hass_storage[DOMAIN]["data"] == snapshot(name="cache")


@pytest.mark.usefixtures("installed_integrations", "setup_integration")
async def test_digest_follows_core_update(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that the releases follow the versions the core update offers."""
    hass.states.async_set(
        MOCK_CORE_UPDATE,
        STATE_ON,
        {ATTR_INSTALLED_VERSION: "2026.7.2", ATTR_LATEST_VERSION: "2026.8.1"},
    )
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": DIGEST})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"]["running"] == "2026.7.2"
    assert msg["result"]["target"] == "2026.8.1"
    assert [r["version"] for r in msg["result"]["releases"]] == ["2026.8"]


@pytest.mark.usefixtures("installed_integrations", "setup_integration")
async def test_digest_no_pending_update(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that nothing is read when no core update is pending."""
    hass.states.async_set(
        MOCK_CORE_UPDATE,
        STATE_OFF,
        {ATTR_INSTALLED_VERSION: "2026.11.0", ATTR_LATEST_VERSION: "2026.11.0"},
    )
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": DIGEST})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"]["target"] is None
    assert msg["result"]["entity_id"] is None
    assert not msg["result"]["releases"]
    assert aioclient_mock.call_count == 0


async def test_digest_without_core_update(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that nothing is read when no update entity offers core versions."""
    # With a Supervisor, no mock is added; here it has no core update yet.
    hass.config.components.add("hassio")
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": DIGEST})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"]["target"] is None
    assert aioclient_mock.call_count == 0


@pytest.mark.usefixtures("installed_integrations")
async def test_digest_supervisor_core_update(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that the Supervisor's core update is used, without adding a mock."""
    hass.config.components.add("hassio")
    core_update = entity_registry.async_get_or_create(
        UPDATE_DOMAIN, "hassio", "home_assistant_core_version_latest"
    )
    hass.states.async_set(
        core_update.entity_id,
        STATE_ON,
        {ATTR_INSTALLED_VERSION: "2026.10.3", ATTR_LATEST_VERSION: "2026.11.0"},
    )
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": DIGEST})
    msg = await client.receive_json()

    assert hass.states.get(MOCK_CORE_UPDATE) is None
    assert msg["result"]["entity_id"] == core_update.entity_id
    assert [r["version"] for r in msg["result"]["releases"]] == ["2026.11"]


@pytest.mark.usefixtures("setup_integration")
async def test_digest_nothing_installed(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that only general changes remain without matching integrations."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": DIGEST})
    msg = await client.receive_json()

    assert msg["success"]
    items = {c["key"]: c["items"] for c in msg["result"]["categories"]}
    assert [(i["title"], i["scope"]) for i in items["breaking"]] == [
        ("Robot vacuums", "global")
    ]
    assert not items["noteworthy"]
    assert not items["quality_scale"]
    assert not items["removed"]


@pytest.mark.parametrize(
    "response",
    [
        pytest.param({"status": 403}, id="rate_limited"),
        pytest.param({"exc": TimeoutError()}, id="timeout"),
        pytest.param({"exc": aiohttp.ClientError()}, id="connection_error"),
    ],
)
@pytest.mark.usefixtures("installed_integrations", "setup_integration")
async def test_digest_release_notes_unavailable(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    response: dict[str, Any],
) -> None:
    """Test the error when the release posts cannot be read."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(POSTS_URL, **response)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": DIGEST})
    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "release_notes_unavailable"
    assert DOMAIN not in hass_storage


@pytest.mark.usefixtures("setup_integration")
async def test_digest_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    """Test that the digest is only available to administrators."""
    client = await hass_ws_client(hass, hass_read_only_access_token)
    await client.send_json_auto_id({"type": DIGEST})
    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "unauthorized"


@pytest.mark.usefixtures("installed_integrations", "setup_integration")
async def test_digest_from_cache(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test that cached releases for the same upgrade are not parsed again."""
    # The cache is read on the first request, not during setup.
    hass_storage[DOMAIN] = {
        "version": 1,
        "key": DOMAIN,
        "data": {
            "key": f"{MOCK_RUNNING}..{MOCK_TARGET}@{INDEX_FORMAT}",
            "indexes": [
                {
                    "version": "2026.9",
                    "url": "https://www.home-assistant.io/blog/2026/09/02/release-20269/",
                    "breaking": [],
                    "noteworthy": [
                        {"title": "MQTT", "domains": ["mqtt"], "text": "Cached."}
                    ],
                    "quality_scale": [],
                    "removed": [],
                }
            ],
        },
    }
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": DIGEST})
    msg = await client.receive_json()

    assert [r["version"] for r in msg["result"]["releases"]] == ["2026.9"]
    noteworthy = msg["result"]["categories"][1]
    assert [i["text"] for i in noteworthy["items"]] == ["Cached."]


@pytest.mark.usefixtures("installed_integrations", "setup_integration")
async def test_digest_rebuilds_outdated_cache(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test that releases cached in an older format are parsed again."""
    hass_storage[DOMAIN] = {
        "version": 1,
        "key": DOMAIN,
        "data": {
            "key": f"{MOCK_RUNNING}..{MOCK_TARGET}@{INDEX_FORMAT - 1}",
            "indexes": [{"version": "2026.9"}],
        },
    }
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": DIGEST})
    msg = await client.receive_json()

    assert [r["version"] for r in msg["result"]["releases"]] == ["2026.8", "2026.11"]
    assert hass_storage[DOMAIN]["data"]["key"].endswith(f"@{INDEX_FORMAT}")
