"""Test supervisor repairs."""

from http import HTTPStatus
import os
from unittest.mock import patch

import pytest

from homeassistant.components.repairs import DOMAIN as REPAIRS_DOMAIN
from homeassistant.core import HomeAssistant
import homeassistant.helpers.issue_registry as ir
from homeassistant.setup import async_setup_component

from .test_init import MOCK_ENVIRON
from .test_issues import mock_resolution_info

from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


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


async def test_supervisor_issue_repair_flow(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test fix flow for supervisor issue."""
    issue_registry: ir.IssueRegistry = ir.async_get(hass)
    mock_resolution_info(
        aioclient_mock,
        issues=[
            {
                "uuid": "1234",
                "type": "multiple_data_disks",
                "context": "system",
                "reference": "/dev/sda1",
                "suggestions": [
                    {
                        "uuid": "1235",
                        "type": "rename_data_disk",
                        "context": "system",
                        "reference": "/dev/sda1",
                    }
                ],
            },
        ],
    )

    result = await async_setup_component(hass, "hassio", {})
    assert result

    repair_issue = issue_registry.async_get_issue(domain="hassio", issue_id="1234")
    assert repair_issue

    client = await hass_client()

    resp = await client.post(
        "/api/repairs/issues/fix",
        json={"handler": "hassio", "issue_id": repair_issue.issue_id},
    )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "type": "form",
        "flow_id": flow_id,
        "handler": "hassio",
        "step_id": "system_rename_data_disk",
        "data_schema": [],
        "errors": None,
        "description_placeholders": {"reference": "/dev/sda1"},
        "last_step": True,
    }

    resp = await client.post(f"/api/repairs/issues/fix/{flow_id}")

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "version": 1,
        "type": "create_entry",
        "flow_id": flow_id,
        "handler": "hassio",
        "description": None,
        "description_placeholders": None,
    }

    assert not issue_registry.async_get_issue(domain="hassio", issue_id="1234")

    assert aioclient_mock.mock_calls[-1][0] == "post"
    assert (
        str(aioclient_mock.mock_calls[-1][1])
        == "http://127.0.0.1/resolution/suggestion/1235"
    )


async def test_supervisor_issue_repair_flow_with_multiple_suggestions(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test fix flow for supervisor issue with multiple suggestions."""
    issue_registry: ir.IssueRegistry = ir.async_get(hass)
    mock_resolution_info(
        aioclient_mock,
        issues=[
            {
                "uuid": "1234",
                "type": "reboot_required",
                "context": "system",
                "reference": "test",
                "suggestions": [
                    {
                        "uuid": "1235",
                        "type": "execute_reboot",
                        "context": "system",
                        "reference": "test",
                    },
                    {
                        "uuid": "1236",
                        "type": "test_type",
                        "context": "system",
                        "reference": "test",
                    },
                ],
            },
        ],
    )

    result = await async_setup_component(hass, "hassio", {})
    assert result

    repair_issue = issue_registry.async_get_issue(domain="hassio", issue_id="1234")
    assert repair_issue

    client = await hass_client()

    resp = await client.post(
        "/api/repairs/issues/fix",
        json={"handler": "hassio", "issue_id": repair_issue.issue_id},
    )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "type": "menu",
        "flow_id": flow_id,
        "handler": "hassio",
        "step_id": "fix_menu",
        "data_schema": [
            {
                "type": "select",
                "options": [
                    ["system_execute_reboot", "system_execute_reboot"],
                    ["system_test_type", "system_test_type"],
                ],
                "name": "next_step_id",
            }
        ],
        "menu_options": ["system_execute_reboot", "system_test_type"],
        "description_placeholders": {"reference": "test"},
    }

    resp = await client.post(
        f"/api/repairs/issues/fix/{flow_id}", json={"next_step_id": "system_test_type"}
    )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "version": 1,
        "type": "create_entry",
        "flow_id": flow_id,
        "handler": "hassio",
        "description": None,
        "description_placeholders": None,
    }

    assert not issue_registry.async_get_issue(domain="hassio", issue_id="1234")

    assert aioclient_mock.mock_calls[-1][0] == "post"
    assert (
        str(aioclient_mock.mock_calls[-1][1])
        == "http://127.0.0.1/resolution/suggestion/1236"
    )


async def test_supervisor_issue_repair_flow_with_multiple_suggestions_and_confirmation(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test fix flow for supervisor issue with multiple suggestions and choice requires confirmation."""
    issue_registry: ir.IssueRegistry = ir.async_get(hass)
    mock_resolution_info(
        aioclient_mock,
        issues=[
            {
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
                    },
                    {
                        "uuid": "1236",
                        "type": "test_type",
                        "context": "system",
                        "reference": None,
                    },
                ],
            },
        ],
    )

    result = await async_setup_component(hass, "hassio", {})
    assert result

    repair_issue = issue_registry.async_get_issue(domain="hassio", issue_id="1234")
    assert repair_issue

    client = await hass_client()

    resp = await client.post(
        "/api/repairs/issues/fix",
        json={"handler": "hassio", "issue_id": repair_issue.issue_id},
    )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "type": "menu",
        "flow_id": flow_id,
        "handler": "hassio",
        "step_id": "fix_menu",
        "data_schema": [
            {
                "type": "select",
                "options": [
                    ["system_execute_reboot", "system_execute_reboot"],
                    ["system_test_type", "system_test_type"],
                ],
                "name": "next_step_id",
            }
        ],
        "menu_options": ["system_execute_reboot", "system_test_type"],
        "description_placeholders": None,
    }

    resp = await client.post(
        f"/api/repairs/issues/fix/{flow_id}",
        json={"next_step_id": "system_execute_reboot"},
    )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "type": "form",
        "flow_id": flow_id,
        "handler": "hassio",
        "step_id": "system_execute_reboot",
        "data_schema": [],
        "errors": None,
        "description_placeholders": None,
        "last_step": True,
    }

    resp = await client.post(f"/api/repairs/issues/fix/{flow_id}")

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "version": 1,
        "type": "create_entry",
        "flow_id": flow_id,
        "handler": "hassio",
        "description": None,
        "description_placeholders": None,
    }

    assert not issue_registry.async_get_issue(domain="hassio", issue_id="1234")

    assert aioclient_mock.mock_calls[-1][0] == "post"
    assert (
        str(aioclient_mock.mock_calls[-1][1])
        == "http://127.0.0.1/resolution/suggestion/1235"
    )


async def test_supervisor_issue_repair_flow_skip_confirmation(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test confirmation skipped for fix flow for supervisor issue with one suggestion."""
    issue_registry: ir.IssueRegistry = ir.async_get(hass)
    mock_resolution_info(
        aioclient_mock,
        issues=[
            {
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
        ],
    )

    result = await async_setup_component(hass, "hassio", {})
    assert result

    repair_issue = issue_registry.async_get_issue(domain="hassio", issue_id="1234")
    assert repair_issue

    client = await hass_client()

    resp = await client.post(
        "/api/repairs/issues/fix",
        json={"handler": "hassio", "issue_id": repair_issue.issue_id},
    )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "type": "form",
        "flow_id": flow_id,
        "handler": "hassio",
        "step_id": "system_execute_reboot",
        "data_schema": [],
        "errors": None,
        "description_placeholders": None,
        "last_step": True,
    }

    resp = await client.post(f"/api/repairs/issues/fix/{flow_id}")

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "version": 1,
        "type": "create_entry",
        "flow_id": flow_id,
        "handler": "hassio",
        "description": None,
        "description_placeholders": None,
    }

    assert not issue_registry.async_get_issue(domain="hassio", issue_id="1234")

    assert aioclient_mock.mock_calls[-1][0] == "post"
    assert (
        str(aioclient_mock.mock_calls[-1][1])
        == "http://127.0.0.1/resolution/suggestion/1235"
    )
