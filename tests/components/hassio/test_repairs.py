"""Test repairs from supervisor issues."""
from __future__ import annotations

import os
from typing import Any
from unittest.mock import ANY, patch

import pytest

from homeassistant.components.repairs import DOMAIN as REPAIRS_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .test_init import MOCK_ENVIRON

from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True)
async def setup_repairs(hass):
    """Set up the repairs integration."""
    assert await async_setup_component(hass, REPAIRS_DOMAIN, {REPAIRS_DOMAIN: {}})


@pytest.fixture(autouse=True)
def mock_all(aioclient_mock: AiohttpClientMocker, request: pytest.FixtureRequest):
    """Mock all setup requests."""
    aioclient_mock.post("http://127.0.0.1/homeassistant/options", json={"result": "ok"})
    aioclient_mock.get("http://127.0.0.1/supervisor/ping", json={"result": "ok"})
    aioclient_mock.post("http://127.0.0.1/supervisor/options", json={"result": "ok"})
    aioclient_mock.get(
        "http://127.0.0.1/info",
        json={
            "result": "ok",
            "data": {
                "supervisor": "222",
                "homeassistant": "0.110.0",
                "hassos": "1.2.3",
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/store",
        json={
            "result": "ok",
            "data": {"addons": [], "repositories": []},
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/host/info",
        json={
            "result": "ok",
            "data": {
                "result": "ok",
                "data": {
                    "chassis": "vm",
                    "operating_system": "Debian GNU/Linux 10 (buster)",
                    "kernel": "4.19.0-6-amd64",
                },
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/core/info",
        json={"result": "ok", "data": {"version_latest": "1.0.0", "version": "1.0.0"}},
    )
    aioclient_mock.get(
        "http://127.0.0.1/os/info",
        json={
            "result": "ok",
            "data": {
                "version_latest": "1.0.0",
                "version": "1.0.0",
                "update_available": False,
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/info",
        json={
            "result": "ok",
            "data": {
                "result": "ok",
                "version": "1.0.0",
                "version_latest": "1.0.0",
                "auto_update": True,
                "addons": [],
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/ingress/panels", json={"result": "ok", "data": {"panels": {}}}
    )
    aioclient_mock.post("http://127.0.0.1/refresh_updates", json={"result": "ok"})


@pytest.fixture(autouse=True)
async def fixture_supervisor_environ():
    """Mock os environ for supervisor."""
    with patch.dict(os.environ, MOCK_ENVIRON):
        yield


def mock_resolution_info(
    aioclient_mock: AiohttpClientMocker,
    unsupported: list[str] | None = None,
    unhealthy: list[str] | None = None,
):
    """Mock resolution/info endpoint with unsupported/unhealthy reasons."""
    aioclient_mock.get(
        "http://127.0.0.1/resolution/info",
        json={
            "result": "ok",
            "data": {
                "unsupported": unsupported or [],
                "unhealthy": unhealthy or [],
                "suggestions": [],
                "issues": [],
                "checks": [
                    {"enabled": True, "slug": "supervisor_trust"},
                    {"enabled": True, "slug": "free_space"},
                ],
            },
        },
    )


def assert_repair_in_list(issues: list[dict[str, Any]], unhealthy: bool, reason: str):
    """Assert repair for unhealthy/unsupported in list."""
    repair_type = "unhealthy" if unhealthy else "unsupported"
    assert {
        "breaks_in_ha_version": None,
        "created": ANY,
        "dismissed_version": None,
        "domain": "hassio",
        "ignored": False,
        "is_fixable": False,
        "issue_id": f"{repair_type}_system_{reason}",
        "issue_domain": None,
        "learn_more_url": f"https://www.home-assistant.io/more-info/{repair_type}/{reason}",
        "severity": "critical" if unhealthy else "warning",
        "translation_key": f"{repair_type}_{reason}",
        "translation_placeholders": None,
    } in issues


async def test_unhealthy_repairs(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test repairs added for unhealthy systems."""
    mock_resolution_info(aioclient_mock, unhealthy=["docker", "setup"])

    result = await async_setup_component(hass, "hassio", {})
    assert result

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 2
    assert_repair_in_list(msg["result"]["issues"], unhealthy=True, reason="docker")
    assert_repair_in_list(msg["result"]["issues"], unhealthy=True, reason="setup")


async def test_unsupported_repairs(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test repairs added for unsupported systems."""
    mock_resolution_info(aioclient_mock, unsupported=["content_trust", "os"])

    result = await async_setup_component(hass, "hassio", {})
    assert result

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 2
    assert_repair_in_list(
        msg["result"]["issues"], unhealthy=False, reason="content_trust"
    )
    assert_repair_in_list(msg["result"]["issues"], unhealthy=False, reason="os")


async def test_unhealthy_repairs_add_remove(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test unhealthy repairs added and removed from dispatches."""
    mock_resolution_info(aioclient_mock)

    result = await async_setup_component(hass, "hassio", {})
    assert result

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": "supervisor/event",
            "data": {
                "event": "health_changed",
                "data": {
                    "healthy": False,
                    "unhealthy_reasons": ["docker"],
                },
            },
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    await hass.async_block_till_done()

    await client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 1
    assert_repair_in_list(msg["result"]["issues"], unhealthy=True, reason="docker")

    await client.send_json(
        {
            "id": 3,
            "type": "supervisor/event",
            "data": {
                "event": "health_changed",
                "data": {"healthy": True},
            },
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    await hass.async_block_till_done()

    await client.send_json({"id": 4, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"issues": []}


async def test_unsupported_repairs_add_remove(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test unsupported repairs added and removed from dispatches."""
    mock_resolution_info(aioclient_mock)

    result = await async_setup_component(hass, "hassio", {})
    assert result

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": "supervisor/event",
            "data": {
                "event": "supported_changed",
                "data": {
                    "supported": False,
                    "unsupported_reasons": ["os"],
                },
            },
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    await hass.async_block_till_done()

    await client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 1
    assert_repair_in_list(msg["result"]["issues"], unhealthy=False, reason="os")

    await client.send_json(
        {
            "id": 3,
            "type": "supervisor/event",
            "data": {
                "event": "supported_changed",
                "data": {"supported": True},
            },
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    await hass.async_block_till_done()

    await client.send_json({"id": 4, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"issues": []}


async def test_reset_repairs_supervisor_restart(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Unsupported/unhealthy repairs reset on supervisor restart."""
    mock_resolution_info(aioclient_mock, unsupported=["os"], unhealthy=["docker"])

    result = await async_setup_component(hass, "hassio", {})
    assert result

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 2
    assert_repair_in_list(msg["result"]["issues"], unhealthy=True, reason="docker")
    assert_repair_in_list(msg["result"]["issues"], unhealthy=False, reason="os")

    aioclient_mock.clear_requests()
    mock_resolution_info(aioclient_mock)
    await client.send_json(
        {
            "id": 2,
            "type": "supervisor/event",
            "data": {
                "event": "supervisor_update",
                "update_key": "supervisor",
                "data": {},
            },
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    await hass.async_block_till_done()

    await client.send_json({"id": 3, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"issues": []}


async def test_reasons_added_and_removed(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test an unsupported/unhealthy reasons being added and removed at same time."""
    mock_resolution_info(aioclient_mock, unsupported=["os"], unhealthy=["docker"])

    result = await async_setup_component(hass, "hassio", {})
    assert result

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 2
    assert_repair_in_list(msg["result"]["issues"], unhealthy=True, reason="docker")
    assert_repair_in_list(msg["result"]["issues"], unhealthy=False, reason="os")

    aioclient_mock.clear_requests()
    mock_resolution_info(
        aioclient_mock, unsupported=["content_trust"], unhealthy=["setup"]
    )
    await client.send_json(
        {
            "id": 2,
            "type": "supervisor/event",
            "data": {
                "event": "supervisor_update",
                "update_key": "supervisor",
                "data": {},
            },
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    await hass.async_block_till_done()

    await client.send_json({"id": 3, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 2
    assert_repair_in_list(msg["result"]["issues"], unhealthy=True, reason="setup")
    assert_repair_in_list(
        msg["result"]["issues"], unhealthy=False, reason="content_trust"
    )


async def test_ignored_unsupported_skipped(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Unsupported reasons which have an identical unhealthy reason are ignored."""
    mock_resolution_info(
        aioclient_mock, unsupported=["privileged"], unhealthy=["privileged"]
    )

    result = await async_setup_component(hass, "hassio", {})
    assert result

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 1
    assert_repair_in_list(msg["result"]["issues"], unhealthy=True, reason="privileged")


async def test_new_unsupported_unhealthy_reason(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """New unsupported/unhealthy reasons result in a generic repair until next core update."""
    mock_resolution_info(
        aioclient_mock, unsupported=["fake_unsupported"], unhealthy=["fake_unhealthy"]
    )

    result = await async_setup_component(hass, "hassio", {})
    assert result

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 2
    assert {
        "breaks_in_ha_version": None,
        "created": ANY,
        "dismissed_version": None,
        "domain": "hassio",
        "ignored": False,
        "is_fixable": False,
        "issue_id": "unhealthy_system_fake_unhealthy",
        "issue_domain": None,
        "learn_more_url": "https://www.home-assistant.io/more-info/unhealthy/fake_unhealthy",
        "severity": "critical",
        "translation_key": "unhealthy",
        "translation_placeholders": {"reason": "fake_unhealthy"},
    } in msg["result"]["issues"]
    assert {
        "breaks_in_ha_version": None,
        "created": ANY,
        "dismissed_version": None,
        "domain": "hassio",
        "ignored": False,
        "is_fixable": False,
        "issue_id": "unsupported_system_fake_unsupported",
        "issue_domain": None,
        "learn_more_url": "https://www.home-assistant.io/more-info/unsupported/fake_unsupported",
        "severity": "warning",
        "translation_key": "unsupported",
        "translation_placeholders": {"reason": "fake_unsupported"},
    } in msg["result"]["issues"]
