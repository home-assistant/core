"""Test supervisor repairs."""

from collections.abc import Generator
from http import HTTPStatus
import os
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from aiohasupervisor import SupervisorError
from aiohasupervisor.models import (
    ContextType,
    Issue,
    IssueType,
    Suggestion,
    SuggestionType,
)
import pytest

from homeassistant.core import HomeAssistant
import homeassistant.helpers.issue_registry as ir
from homeassistant.setup import async_setup_component

from .test_init import MOCK_ENVIRON
from .test_issues import mock_resolution_info

from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
def fixture_supervisor_environ() -> Generator[None]:
    """Mock os environ for supervisor."""
    with patch.dict(os.environ, MOCK_ENVIRON):
        yield


@pytest.mark.usefixtures("all_setup_requests")
async def test_supervisor_issue_repair_flow(
    hass: HomeAssistant,
    supervisor_client: AsyncMock,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test fix flow for supervisor issue."""
    mock_resolution_info(
        supervisor_client,
        issues=[
            Issue(
                type=IssueType.MULTIPLE_DATA_DISKS,
                context=ContextType.SYSTEM,
                reference="/dev/sda1",
                uuid=(issue_uuid := uuid4()),
            ),
        ],
        suggestions_by_issue={
            issue_uuid: [
                Suggestion(
                    type=SuggestionType.RENAME_DATA_DISK,
                    context=ContextType.SYSTEM,
                    reference="/dev/sda1",
                    uuid=(sugg_uuid := uuid4()),
                    auto=False,
                )
            ]
        },
    )

    assert await async_setup_component(hass, "hassio", {})

    repair_issue = issue_registry.async_get_issue(
        domain="hassio", issue_id=issue_uuid.hex
    )
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
        "preview": None,
    }

    resp = await client.post(f"/api/repairs/issues/fix/{flow_id}")

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "type": "create_entry",
        "flow_id": flow_id,
        "handler": "hassio",
        "description": None,
        "description_placeholders": None,
    }

    assert not issue_registry.async_get_issue(domain="hassio", issue_id=issue_uuid.hex)
    supervisor_client.resolution.apply_suggestion.assert_called_once_with(sugg_uuid)


@pytest.mark.usefixtures("all_setup_requests")
async def test_supervisor_issue_repair_flow_with_multiple_suggestions(
    hass: HomeAssistant,
    supervisor_client: AsyncMock,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test fix flow for supervisor issue with multiple suggestions."""
    mock_resolution_info(
        supervisor_client,
        issues=[
            Issue(
                type=IssueType.REBOOT_REQUIRED,
                context=ContextType.SYSTEM,
                reference="test",
                uuid=(issue_uuid := uuid4()),
            ),
        ],
        suggestions_by_issue={
            issue_uuid: [
                Suggestion(
                    type=SuggestionType.EXECUTE_REBOOT,
                    context=ContextType.SYSTEM,
                    reference="test",
                    uuid=uuid4(),
                    auto=False,
                ),
                Suggestion(
                    type="test_type",
                    context=ContextType.SYSTEM,
                    reference="test",
                    uuid=(sugg_uuid := uuid4()),
                    auto=False,
                ),
            ]
        },
    )

    assert await async_setup_component(hass, "hassio", {})

    repair_issue = issue_registry.async_get_issue(
        domain="hassio", issue_id=issue_uuid.hex
    )
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
        "type": "create_entry",
        "flow_id": flow_id,
        "handler": "hassio",
        "description": None,
        "description_placeholders": None,
    }

    assert not issue_registry.async_get_issue(domain="hassio", issue_id=issue_uuid.hex)
    supervisor_client.resolution.apply_suggestion.assert_called_once_with(sugg_uuid)


@pytest.mark.usefixtures("all_setup_requests")
async def test_supervisor_issue_repair_flow_with_multiple_suggestions_and_confirmation(
    hass: HomeAssistant,
    supervisor_client: AsyncMock,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test fix flow for supervisor issue with multiple suggestions and choice requires confirmation."""
    mock_resolution_info(
        supervisor_client,
        issues=[
            Issue(
                type=IssueType.REBOOT_REQUIRED,
                context=ContextType.SYSTEM,
                reference=None,
                uuid=(issue_uuid := uuid4()),
            ),
        ],
        suggestions_by_issue={
            issue_uuid: [
                Suggestion(
                    type=SuggestionType.EXECUTE_REBOOT,
                    context=ContextType.SYSTEM,
                    reference=None,
                    uuid=(sugg_uuid := uuid4()),
                    auto=False,
                ),
                Suggestion(
                    type="test_type",
                    context=ContextType.SYSTEM,
                    reference=None,
                    uuid=uuid4(),
                    auto=False,
                ),
            ]
        },
    )

    assert await async_setup_component(hass, "hassio", {})

    repair_issue = issue_registry.async_get_issue(
        domain="hassio", issue_id=issue_uuid.hex
    )
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
        "preview": None,
    }

    resp = await client.post(f"/api/repairs/issues/fix/{flow_id}")

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "type": "create_entry",
        "flow_id": flow_id,
        "handler": "hassio",
        "description": None,
        "description_placeholders": None,
    }

    assert not issue_registry.async_get_issue(domain="hassio", issue_id=issue_uuid.hex)
    supervisor_client.resolution.apply_suggestion.assert_called_once_with(sugg_uuid)


@pytest.mark.usefixtures("all_setup_requests")
async def test_supervisor_issue_repair_flow_skip_confirmation(
    hass: HomeAssistant,
    supervisor_client: AsyncMock,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test confirmation skipped for fix flow for supervisor issue with one suggestion."""
    mock_resolution_info(
        supervisor_client,
        issues=[
            Issue(
                type=IssueType.REBOOT_REQUIRED,
                context=ContextType.SYSTEM,
                reference=None,
                uuid=(issue_uuid := uuid4()),
            ),
        ],
        suggestions_by_issue={
            issue_uuid: [
                Suggestion(
                    type=SuggestionType.EXECUTE_REBOOT,
                    context=ContextType.SYSTEM,
                    reference=None,
                    uuid=(sugg_uuid := uuid4()),
                    auto=False,
                ),
            ]
        },
    )

    assert await async_setup_component(hass, "hassio", {})

    repair_issue = issue_registry.async_get_issue(
        domain="hassio", issue_id=issue_uuid.hex
    )
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
        "preview": None,
    }

    resp = await client.post(f"/api/repairs/issues/fix/{flow_id}")

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "type": "create_entry",
        "flow_id": flow_id,
        "handler": "hassio",
        "description": None,
        "description_placeholders": None,
    }

    assert not issue_registry.async_get_issue(domain="hassio", issue_id=issue_uuid.hex)
    supervisor_client.resolution.apply_suggestion.assert_called_once_with(sugg_uuid)


@pytest.mark.usefixtures("all_setup_requests")
async def test_mount_failed_repair_flow_error(
    hass: HomeAssistant,
    supervisor_client: AsyncMock,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test repair flow fails when repair fails to apply."""
    mock_resolution_info(
        supervisor_client,
        issues=[
            Issue(
                type=IssueType.MOUNT_FAILED,
                context=ContextType.MOUNT,
                reference="backup_share",
                uuid=(issue_uuid := uuid4()),
            ),
        ],
        suggestions_by_issue={
            issue_uuid: [
                Suggestion(
                    type=SuggestionType.EXECUTE_RELOAD,
                    context=ContextType.MOUNT,
                    reference="backup_share",
                    uuid=uuid4(),
                    auto=False,
                ),
                Suggestion(
                    type=SuggestionType.EXECUTE_REMOVE,
                    context=ContextType.MOUNT,
                    reference="backup_share",
                    uuid=uuid4(),
                    auto=False,
                ),
            ]
        },
        suggestion_result=SupervisorError("boom"),
    )

    assert await async_setup_component(hass, "hassio", {})

    repair_issue = issue_registry.async_get_issue(
        domain="hassio", issue_id=issue_uuid.hex
    )
    assert repair_issue

    client = await hass_client()

    resp = await client.post(
        "/api/repairs/issues/fix",
        json={"handler": "hassio", "issue_id": repair_issue.issue_id},
    )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    flow_id = data["flow_id"]

    resp = await client.post(
        f"/api/repairs/issues/fix/{flow_id}",
        json={"next_step_id": "mount_execute_reload"},
    )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "type": "abort",
        "flow_id": flow_id,
        "handler": "hassio",
        "reason": "apply_suggestion_fail",
        "result": None,
        "description_placeholders": None,
    }

    assert issue_registry.async_get_issue(domain="hassio", issue_id=issue_uuid.hex)


@pytest.mark.usefixtures("all_setup_requests")
async def test_mount_failed_repair_flow(
    hass: HomeAssistant,
    supervisor_client: AsyncMock,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test repair flow for mount_failed issue."""
    mock_resolution_info(
        supervisor_client,
        issues=[
            Issue(
                type=IssueType.MOUNT_FAILED,
                context=ContextType.MOUNT,
                reference="backup_share",
                uuid=(issue_uuid := uuid4()),
            ),
        ],
        suggestions_by_issue={
            issue_uuid: [
                Suggestion(
                    type=SuggestionType.EXECUTE_RELOAD,
                    context=ContextType.MOUNT,
                    reference="backup_share",
                    uuid=(sugg_uuid := uuid4()),
                    auto=False,
                ),
                Suggestion(
                    type=SuggestionType.EXECUTE_REMOVE,
                    context=ContextType.MOUNT,
                    reference="backup_share",
                    uuid=uuid4(),
                    auto=False,
                ),
            ]
        },
    )

    assert await async_setup_component(hass, "hassio", {})

    repair_issue = issue_registry.async_get_issue(
        domain="hassio", issue_id=issue_uuid.hex
    )
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
                    ["mount_execute_reload", "mount_execute_reload"],
                    ["mount_execute_remove", "mount_execute_remove"],
                ],
                "name": "next_step_id",
            }
        ],
        "menu_options": ["mount_execute_reload", "mount_execute_remove"],
        "description_placeholders": {
            "reference": "backup_share",
            "storage_url": "/config/storage",
        },
    }

    resp = await client.post(
        f"/api/repairs/issues/fix/{flow_id}",
        json={"next_step_id": "mount_execute_reload"},
    )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "type": "create_entry",
        "flow_id": flow_id,
        "handler": "hassio",
        "description": None,
        "description_placeholders": None,
    }

    assert not issue_registry.async_get_issue(domain="hassio", issue_id=issue_uuid.hex)
    supervisor_client.resolution.apply_suggestion.assert_called_once_with(sugg_uuid)


@pytest.mark.parametrize(
    "all_setup_requests", [{"include_addons": True}], indirect=True
)
@pytest.mark.usefixtures("all_setup_requests")
async def test_supervisor_issue_docker_config_repair_flow(
    hass: HomeAssistant,
    supervisor_client: AsyncMock,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test fix flow for supervisor issue."""
    mock_resolution_info(
        supervisor_client,
        issues=[
            Issue(
                type=IssueType.DOCKER_CONFIG,
                context=ContextType.SYSTEM,
                reference=None,
                uuid=(issue1_uuid := uuid4()),
            ),
            Issue(
                type=IssueType.DOCKER_CONFIG,
                context=ContextType.CORE,
                reference=None,
                uuid=(issue2_uuid := uuid4()),
            ),
            Issue(
                type=IssueType.DOCKER_CONFIG,
                context=ContextType.ADDON,
                reference="test",
                uuid=(issue3_uuid := uuid4()),
            ),
        ],
        suggestions_by_issue={
            issue1_uuid: [
                Suggestion(
                    type=SuggestionType.EXECUTE_REBUILD,
                    context=ContextType.SYSTEM,
                    reference=None,
                    uuid=(sugg_uuid := uuid4()),
                    auto=False,
                ),
            ],
            issue2_uuid: [
                Suggestion(
                    type=SuggestionType.EXECUTE_REBUILD,
                    context=ContextType.CORE,
                    reference=None,
                    uuid=uuid4(),
                    auto=False,
                ),
            ],
            issue3_uuid: [
                Suggestion(
                    type=SuggestionType.EXECUTE_REBUILD,
                    context=ContextType.ADDON,
                    reference="test",
                    uuid=uuid4(),
                    auto=False,
                ),
            ],
        },
    )

    assert await async_setup_component(hass, "hassio", {})

    repair_issue = issue_registry.async_get_issue(
        domain="hassio", issue_id=issue1_uuid.hex
    )
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
        "step_id": "system_execute_rebuild",
        "data_schema": [],
        "errors": None,
        "description_placeholders": {"components": "Home Assistant\n- test"},
        "last_step": True,
        "preview": None,
    }

    resp = await client.post(f"/api/repairs/issues/fix/{flow_id}")

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "type": "create_entry",
        "flow_id": flow_id,
        "handler": "hassio",
        "description": None,
        "description_placeholders": None,
    }

    assert not issue_registry.async_get_issue(domain="hassio", issue_id=issue1_uuid.hex)
    supervisor_client.resolution.apply_suggestion.assert_called_once_with(sugg_uuid)


@pytest.mark.usefixtures("all_setup_requests")
async def test_supervisor_issue_repair_flow_multiple_data_disks(
    hass: HomeAssistant,
    supervisor_client: AsyncMock,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test fix flow for multiple data disks supervisor issue."""
    mock_resolution_info(
        supervisor_client,
        issues=[
            Issue(
                type=IssueType.MULTIPLE_DATA_DISKS,
                context=ContextType.SYSTEM,
                reference="/dev/sda1",
                uuid=(issue_uuid := uuid4()),
            ),
        ],
        suggestions_by_issue={
            issue_uuid: [
                Suggestion(
                    type=SuggestionType.RENAME_DATA_DISK,
                    context=ContextType.SYSTEM,
                    reference="/dev/sda1",
                    uuid=uuid4(),
                    auto=False,
                ),
                Suggestion(
                    type=SuggestionType.ADOPT_DATA_DISK,
                    context=ContextType.SYSTEM,
                    reference="/dev/sda1",
                    uuid=(sugg_uuid := uuid4()),
                    auto=False,
                ),
            ]
        },
    )

    assert await async_setup_component(hass, "hassio", {})

    repair_issue = issue_registry.async_get_issue(
        domain="hassio", issue_id=issue_uuid.hex
    )
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
                    ["system_rename_data_disk", "system_rename_data_disk"],
                    ["system_adopt_data_disk", "system_adopt_data_disk"],
                ],
                "name": "next_step_id",
            }
        ],
        "menu_options": ["system_rename_data_disk", "system_adopt_data_disk"],
        "description_placeholders": {"reference": "/dev/sda1"},
    }

    resp = await client.post(
        f"/api/repairs/issues/fix/{flow_id}",
        json={"next_step_id": "system_adopt_data_disk"},
    )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "type": "form",
        "flow_id": flow_id,
        "handler": "hassio",
        "step_id": "system_adopt_data_disk",
        "data_schema": [],
        "errors": None,
        "description_placeholders": {"reference": "/dev/sda1"},
        "last_step": True,
        "preview": None,
    }

    resp = await client.post(f"/api/repairs/issues/fix/{flow_id}")

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "type": "create_entry",
        "flow_id": flow_id,
        "handler": "hassio",
        "description": None,
        "description_placeholders": None,
    }

    assert not issue_registry.async_get_issue(domain="hassio", issue_id=issue_uuid.hex)
    supervisor_client.resolution.apply_suggestion.assert_called_once_with(sugg_uuid)


@pytest.mark.parametrize(
    "all_setup_requests", [{"include_addons": True}], indirect=True
)
@pytest.mark.usefixtures("all_setup_requests")
async def test_supervisor_issue_detached_addon_removed(
    hass: HomeAssistant,
    supervisor_client: AsyncMock,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test fix flow for supervisor issue."""
    mock_resolution_info(
        supervisor_client,
        issues=[
            Issue(
                type=IssueType.DETACHED_ADDON_REMOVED,
                context=ContextType.ADDON,
                reference="test",
                uuid=(issue_uuid := uuid4()),
            ),
        ],
        suggestions_by_issue={
            issue_uuid: [
                Suggestion(
                    type=SuggestionType.EXECUTE_REMOVE,
                    context=ContextType.ADDON,
                    reference="test",
                    uuid=(sugg_uuid := uuid4()),
                    auto=False,
                ),
            ]
        },
    )

    assert await async_setup_component(hass, "hassio", {})

    repair_issue = issue_registry.async_get_issue(
        domain="hassio", issue_id=issue_uuid.hex
    )
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
        "step_id": "addon_execute_remove",
        "data_schema": [],
        "errors": None,
        "description_placeholders": {
            "reference": "test",
            "addon": "test",
            "help_url": "https://www.home-assistant.io/help/",
            "community_url": "https://community.home-assistant.io/",
        },
        "last_step": True,
        "preview": None,
    }

    resp = await client.post(f"/api/repairs/issues/fix/{flow_id}")

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "type": "create_entry",
        "flow_id": flow_id,
        "handler": "hassio",
        "description": None,
        "description_placeholders": None,
    }

    assert not issue_registry.async_get_issue(domain="hassio", issue_id=issue_uuid.hex)
    supervisor_client.resolution.apply_suggestion.assert_called_once_with(sugg_uuid)


@pytest.mark.parametrize(
    "all_setup_requests", [{"include_addons": True}], indirect=True
)
@pytest.mark.usefixtures("all_setup_requests")
async def test_supervisor_issue_addon_boot_fail(
    hass: HomeAssistant,
    supervisor_client: AsyncMock,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test fix flow for supervisor issue."""
    mock_resolution_info(
        supervisor_client,
        issues=[
            Issue(
                type="boot_fail",
                context=ContextType.ADDON,
                reference="test",
                uuid=(issue_uuid := uuid4()),
            ),
        ],
        suggestions_by_issue={
            issue_uuid: [
                Suggestion(
                    type="execute_start",
                    context=ContextType.ADDON,
                    reference="test",
                    uuid=(sugg_uuid := uuid4()),
                    auto=False,
                ),
                Suggestion(
                    type="disable_boot",
                    context=ContextType.ADDON,
                    reference="test",
                    uuid=uuid4(),
                    auto=False,
                ),
            ]
        },
    )

    assert await async_setup_component(hass, "hassio", {})

    repair_issue = issue_registry.async_get_issue(
        domain="hassio", issue_id=issue_uuid.hex
    )
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
                    ["addon_execute_start", "addon_execute_start"],
                    ["addon_disable_boot", "addon_disable_boot"],
                ],
                "name": "next_step_id",
            }
        ],
        "menu_options": ["addon_execute_start", "addon_disable_boot"],
        "description_placeholders": {
            "reference": "test",
            "addon": "test",
        },
    }

    resp = await client.post(
        f"/api/repairs/issues/fix/{flow_id}",
        json={"next_step_id": "addon_execute_start"},
    )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "type": "create_entry",
        "flow_id": flow_id,
        "handler": "hassio",
        "description": None,
        "description_placeholders": None,
    }

    assert not issue_registry.async_get_issue(domain="hassio", issue_id=issue_uuid.hex)
    supervisor_client.resolution.apply_suggestion.assert_called_once_with(sugg_uuid)
