"""Test issues from supervisor issues."""
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
async def mock_all(all_setup_requests):
    """Mock all setup requests."""


@pytest.fixture(autouse=True)
async def fixture_supervisor_environ():
    """Mock os environ for supervisor."""
    with patch.dict(os.environ, MOCK_ENVIRON):
        yield


def mock_resolution_info(
    aioclient_mock: AiohttpClientMocker,
    unsupported: list[str] | None = None,
    unhealthy: list[str] | None = None,
    issues: list[dict[str, str]] | None = None,
):
    """Mock resolution/info endpoint with unsupported/unhealthy reasons and/or issues."""
    aioclient_mock.get(
        "http://127.0.0.1/resolution/info",
        json={
            "result": "ok",
            "data": {
                "unsupported": unsupported or [],
                "unhealthy": unhealthy or [],
                "suggestions": [],
                "issues": [
                    {k: v for k, v in issue.items() if k != "suggestions"}
                    for issue in issues
                ]
                if issues
                else [],
                "checks": [
                    {"enabled": True, "slug": "supervisor_trust"},
                    {"enabled": True, "slug": "free_space"},
                ],
            },
        },
    )

    if issues:
        suggestions_by_issue = {
            issue["uuid"]: issue.get("suggestions", []) for issue in issues
        }
        for issue_uuid, suggestions in suggestions_by_issue.items():
            aioclient_mock.get(
                f"http://127.0.0.1/resolution/issue/{issue_uuid}/suggestions",
                json={"result": "ok", "data": {"suggestions": suggestions}},
            )
            for suggestion in suggestions:
                aioclient_mock.post(
                    f"http://127.0.0.1/resolution/suggestion/{suggestion['uuid']}",
                    json={"result": "ok"},
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


def assert_issue_repair_in_list(
    issues: list[dict[str, Any]],
    uuid: str,
    context: str,
    type_: str,
    fixable: bool,
    reference: str | None,
):
    """Assert repair for unhealthy/unsupported in list."""
    assert {
        "breaks_in_ha_version": None,
        "created": ANY,
        "dismissed_version": None,
        "domain": "hassio",
        "ignored": False,
        "is_fixable": fixable,
        "issue_id": uuid,
        "issue_domain": None,
        "learn_more_url": None,
        "severity": "warning",
        "translation_key": f"issue_{context}_{type_}",
        "translation_placeholders": {"reference": reference} if reference else None,
    } in issues


async def test_unhealthy_issues(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test issues added for unhealthy systems."""
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


async def test_unsupported_issues(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test issues added for unsupported systems."""
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


async def test_unhealthy_issues_add_remove(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test unhealthy issues added and removed from dispatches."""
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


async def test_unsupported_issues_add_remove(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test unsupported issues added and removed from dispatches."""
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


async def test_reset_issues_supervisor_restart(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """All issues reset on supervisor restart."""
    mock_resolution_info(
        aioclient_mock,
        unsupported=["os"],
        unhealthy=["docker"],
        issues=[
            {
                "uuid": "1234",
                "type": "reboot_required",
                "context": "system",
                "reference": None,
            }
        ],
    )

    result = await async_setup_component(hass, "hassio", {})
    assert result

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 3
    assert_repair_in_list(msg["result"]["issues"], unhealthy=True, reason="docker")
    assert_repair_in_list(msg["result"]["issues"], unhealthy=False, reason="os")
    assert_issue_repair_in_list(
        msg["result"]["issues"],
        uuid="1234",
        context="system",
        type_="reboot_required",
        fixable=False,
        reference=None,
    )

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


async def test_supervisor_issues(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test repairs added for supervisor issue."""
    mock_resolution_info(
        aioclient_mock,
        issues=[
            {
                "uuid": "1234",
                "type": "reboot_required",
                "context": "system",
                "reference": None,
            },
            {
                "uuid": "1235",
                "type": "multiple_data_disks",
                "context": "system",
                "reference": "/dev/sda1",
                "suggestions": [
                    {
                        "uuid": "1236",
                        "type": "rename_data_disk",
                        "context": "system",
                        "reference": "/dev/sda1",
                    }
                ],
            },
            {
                "uuid": "1237",
                "type": "should_not_be_repair",
                "context": "os",
                "reference": None,
            },
        ],
    )

    result = await async_setup_component(hass, "hassio", {})
    assert result

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 2
    assert_issue_repair_in_list(
        msg["result"]["issues"],
        uuid="1234",
        context="system",
        type_="reboot_required",
        fixable=False,
        reference=None,
    )
    assert_issue_repair_in_list(
        msg["result"]["issues"],
        uuid="1235",
        context="system",
        type_="multiple_data_disks",
        fixable=True,
        reference="/dev/sda1",
    )


async def test_supervisor_issues_add_remove(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test supervisor issues added and removed from dispatches."""
    mock_resolution_info(aioclient_mock)

    result = await async_setup_component(hass, "hassio", {})
    assert result

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": "supervisor/event",
            "data": {
                "event": "issue_changed",
                "data": {
                    "uuid": "1234",
                    "type": "reboot_required",
                    "context": "system",
                    "reference": None,
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
    assert_issue_repair_in_list(
        msg["result"]["issues"],
        uuid="1234",
        context="system",
        type_="reboot_required",
        fixable=False,
        reference=None,
    )

    await client.send_json(
        {
            "id": 3,
            "type": "supervisor/event",
            "data": {
                "event": "issue_changed",
                "data": {
                    "uuid": "1234",
                    "type": "reboot_required",
                    "context": "system",
                    "reference": None,
                    "suggestions": [
                        {
                            "uuid": "1235",
                            "type": "execute_reboot",
                            "context": "system",
                            "reference": None,
                        }
                    ],
                },
            },
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    await hass.async_block_till_done()

    await client.send_json({"id": 4, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 1
    assert_issue_repair_in_list(
        msg["result"]["issues"],
        uuid="1234",
        context="system",
        type_="reboot_required",
        fixable=True,
        reference=None,
    )

    await client.send_json(
        {
            "id": 5,
            "type": "supervisor/event",
            "data": {
                "event": "issue_removed",
                "data": {
                    "uuid": "1234",
                    "type": "reboot_required",
                    "context": "system",
                    "reference": None,
                },
            },
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    await hass.async_block_till_done()

    await client.send_json({"id": 6, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"issues": []}


async def test_supervisor_issues_suggestions_fail(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test failing to get suggestions for issue skips it."""
    aioclient_mock.get(
        "http://127.0.0.1/resolution/info",
        json={
            "result": "ok",
            "data": {
                "unsupported": [],
                "unhealthy": [],
                "suggestions": [],
                "issues": [
                    {
                        "uuid": "1234",
                        "type": "reboot_required",
                        "context": "system",
                        "reference": None,
                    }
                ],
                "checks": [
                    {"enabled": True, "slug": "supervisor_trust"},
                    {"enabled": True, "slug": "free_space"},
                ],
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/resolution/issue/1234/suggestions",
        exc=TimeoutError(),
    )

    result = await async_setup_component(hass, "hassio", {})
    assert result

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 0


async def test_supervisor_remove_missing_issue_without_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test HA skips message to remove issue that it didn't know about (sync issue)."""
    mock_resolution_info(aioclient_mock)

    result = await async_setup_component(hass, "hassio", {})
    assert result

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 5,
            "type": "supervisor/event",
            "data": {
                "event": "issue_removed",
                "data": {
                    "uuid": "1234",
                    "type": "reboot_required",
                    "context": "system",
                    "reference": None,
                },
            },
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    await hass.async_block_till_done()


async def test_system_is_not_ready(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Ensure hassio starts despite error."""
    aioclient_mock.get(
        "http://127.0.0.1/resolution/info",
        json={
            "result": "",
            "message": "System is not ready with state: setup",
        },
    )

    assert await async_setup_component(hass, "hassio", {})
    assert "Failed to update supervisor issues" in caplog.text
