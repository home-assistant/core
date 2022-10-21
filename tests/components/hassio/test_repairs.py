"""Test repairs from supervisor issues."""

from __future__ import annotations

import os
from unittest.mock import ANY, patch

import pytest

from homeassistant.components.hassio.const import ATTR_WS_EVENT, EVENT_SUPERVISOR_EVENT
from homeassistant.components.repairs import DOMAIN as REPAIRS_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.setup import async_setup_component

from .test_init import MOCK_ENVIRON

from tests.common import async_mock_signal
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(autouse=True)
async def setup_repairs(hass):
    """Set up the repairs integration."""
    assert await async_setup_component(hass, REPAIRS_DOMAIN, {REPAIRS_DOMAIN: {}})


@pytest.fixture(autouse=True)
def mock_all(aioclient_mock, request):
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


async def test_unhealthy_repairs(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client,
):
    """Test repairs added for unhealthy systems."""
    mock_resolution_info(aioclient_mock, unhealthy=["docker", "setup"])

    result = await async_setup_component(hass, "hassio", {})
    assert result

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert {
        "breaks_in_ha_version": None,
        "created": ANY,
        "dismissed_version": None,
        "domain": "hassio",
        "ignored": False,
        "is_fixable": False,
        "issue_id": "unhealthy_system_docker",
        "issue_domain": None,
        "learn_more_url": "https://www.home-assistant.io/more-info/unhealthy/docker",
        "severity": "critical",
        "translation_key": "unhealthy",
        "translation_placeholders": {
            "reason": "docker",
        },
    } in msg["result"]["issues"]
    assert {
        "breaks_in_ha_version": None,
        "created": ANY,
        "dismissed_version": None,
        "domain": "hassio",
        "ignored": False,
        "is_fixable": False,
        "issue_id": "unhealthy_system_setup",
        "issue_domain": None,
        "learn_more_url": "https://www.home-assistant.io/more-info/unhealthy/setup",
        "severity": "critical",
        "translation_key": "unhealthy",
        "translation_placeholders": {
            "reason": "setup",
        },
    } in msg["result"]["issues"]


async def test_unsupported_repairs(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client,
):
    """Test repairs added for unsupported systems."""
    mock_resolution_info(aioclient_mock, unsupported=["content_trust", "os"])

    result = await async_setup_component(hass, "hassio", {})
    assert result

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert {
        "breaks_in_ha_version": None,
        "created": ANY,
        "dismissed_version": None,
        "domain": "hassio",
        "ignored": False,
        "is_fixable": False,
        "issue_id": "unsupported_system_content_trust",
        "issue_domain": None,
        "learn_more_url": "https://www.home-assistant.io/more-info/unsupported/content_trust",
        "severity": "warning",
        "translation_key": "unsupported",
        "translation_placeholders": {
            "reason": "content_trust",
        },
    } in msg["result"]["issues"]
    assert {
        "breaks_in_ha_version": None,
        "created": ANY,
        "dismissed_version": None,
        "domain": "hassio",
        "ignored": False,
        "is_fixable": False,
        "issue_id": "unsupported_system_os",
        "issue_domain": None,
        "learn_more_url": "https://www.home-assistant.io/more-info/unsupported/os",
        "severity": "warning",
        "translation_key": "unsupported",
        "translation_placeholders": {
            "reason": "os",
        },
    } in msg["result"]["issues"]


async def test_unhealthy_repairs_add_remove(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client,
):
    """Test unhealthy repairs added and removed from dispatches."""
    mock_resolution_info(aioclient_mock)

    result = await async_setup_component(hass, "hassio", {})
    assert result

    client = await hass_ws_client(hass)

    calls = async_mock_signal(hass, EVENT_SUPERVISOR_EVENT)
    async_dispatcher_send(
        hass,
        EVENT_SUPERVISOR_EVENT,
        {
            ATTR_WS_EVENT: "health_changed",
            "data": {
                "healthy": False,
                "unhealthy_reasons": ["docker"],
            },
        },
    )
    assert len(calls) == 1

    await client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            {
                "breaks_in_ha_version": None,
                "created": ANY,
                "dismissed_version": None,
                "domain": "hassio",
                "ignored": False,
                "is_fixable": False,
                "issue_id": "unhealthy_system_docker",
                "issue_domain": None,
                "learn_more_url": "https://www.home-assistant.io/more-info/unhealthy/docker",
                "severity": "critical",
                "translation_key": "unhealthy",
                "translation_placeholders": {
                    "reason": "docker",
                },
            },
        ]
    }

    async_dispatcher_send(
        hass,
        EVENT_SUPERVISOR_EVENT,
        {
            ATTR_WS_EVENT: "health_changed",
            "data": {
                "healthy": True,
            },
        },
    )
    assert len(calls) == 2

    await client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"issues": []}


async def test_unsupported_repairs_add_remove(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client,
):
    """Test unsupported repairs added and removed from dispatches."""
    mock_resolution_info(aioclient_mock)

    result = await async_setup_component(hass, "hassio", {})
    assert result

    client = await hass_ws_client(hass)

    calls = async_mock_signal(hass, EVENT_SUPERVISOR_EVENT)
    async_dispatcher_send(
        hass,
        EVENT_SUPERVISOR_EVENT,
        {
            ATTR_WS_EVENT: "supported_changed",
            "data": {
                "supported": False,
                "unsupported_reasons": ["os"],
            },
        },
    )
    assert len(calls) == 1

    await client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            {
                "breaks_in_ha_version": None,
                "created": ANY,
                "dismissed_version": None,
                "domain": "hassio",
                "ignored": False,
                "is_fixable": False,
                "issue_id": "unsupported_system_os",
                "issue_domain": None,
                "learn_more_url": "https://www.home-assistant.io/more-info/unsupported/os",
                "severity": "warning",
                "translation_key": "unsupported",
                "translation_placeholders": {
                    "reason": "os",
                },
            },
        ]
    }

    async_dispatcher_send(
        hass,
        EVENT_SUPERVISOR_EVENT,
        {
            ATTR_WS_EVENT: "supported_changed",
            "data": {
                "supported": True,
            },
        },
    )
    assert len(calls) == 2

    await client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"issues": []}


async def test_reset_repairs_supervisor_restart(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client,
):
    """Unsupported/unhealthy repairs reset on supervisor restart."""
    mock_resolution_info(aioclient_mock, unsupported=["os"], unhealthy=["docker"])

    result = await async_setup_component(hass, "hassio", {})
    assert result

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert {
        "breaks_in_ha_version": None,
        "created": ANY,
        "dismissed_version": None,
        "domain": "hassio",
        "ignored": False,
        "is_fixable": False,
        "issue_id": "unhealthy_system_docker",
        "issue_domain": None,
        "learn_more_url": "https://www.home-assistant.io/more-info/unhealthy/docker",
        "severity": "critical",
        "translation_key": "unhealthy",
        "translation_placeholders": {
            "reason": "docker",
        },
    } in msg["result"]["issues"]
    assert {
        "breaks_in_ha_version": None,
        "created": ANY,
        "dismissed_version": None,
        "domain": "hassio",
        "ignored": False,
        "is_fixable": False,
        "issue_id": "unsupported_system_os",
        "issue_domain": None,
        "learn_more_url": "https://www.home-assistant.io/more-info/unsupported/os",
        "severity": "warning",
        "translation_key": "unsupported",
        "translation_placeholders": {
            "reason": "os",
        },
    } in msg["result"]["issues"]

    aioclient_mock.clear_requests()
    mock_resolution_info(aioclient_mock)
    calls = async_mock_signal(hass, EVENT_SUPERVISOR_EVENT)
    async_dispatcher_send(
        hass,
        EVENT_SUPERVISOR_EVENT,
        {
            ATTR_WS_EVENT: "supervisor_update",
            "update_key": "supervisor",
            "data": {},
        },
    )
    assert len(calls) == 1

    await client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"issues": []}
