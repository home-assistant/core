"""Test issues from supervisor issues."""

from __future__ import annotations

from collections.abc import Generator
from datetime import timedelta
import os
from typing import Any
from unittest.mock import ANY, AsyncMock, patch
from uuid import UUID, uuid4

from aiohasupervisor import (
    SupervisorBadRequestError,
    SupervisorError,
    SupervisorTimeoutError,
)
from aiohasupervisor.models import (
    Check,
    CheckType,
    ContextType,
    Issue,
    IssueType,
    ResolutionInfo,
    Suggestion,
    SuggestionType,
    UnhealthyReason,
    UnsupportedReason,
)
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.repairs import DOMAIN as REPAIRS_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .test_init import MOCK_ENVIRON

from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True)
async def setup_repairs(hass: HomeAssistant) -> None:
    """Set up the repairs integration."""
    assert await async_setup_component(hass, REPAIRS_DOMAIN, {REPAIRS_DOMAIN: {}})


@pytest.fixture(autouse=True)
def fixture_supervisor_environ() -> Generator[None]:
    """Mock os environ for supervisor."""
    with patch.dict(os.environ, MOCK_ENVIRON):
        yield


def mock_resolution_info(
    supervisor_client: AsyncMock,
    unsupported: list[UnsupportedReason] | None = None,
    unhealthy: list[UnhealthyReason] | None = None,
    issues: list[Issue] | None = None,
    suggestions_by_issue: dict[UUID, list[Suggestion]] | None = None,
    suggestion_result: SupervisorError | None = None,
) -> None:
    """Mock resolution/info endpoint with unsupported/unhealthy reasons and/or issues."""
    supervisor_client.resolution.info.return_value = ResolutionInfo(
        unsupported=unsupported or [],
        unhealthy=unhealthy or [],
        issues=issues or [],
        suggestions=[
            suggestion
            for issue_list in suggestions_by_issue.values()
            for suggestion in issue_list
        ]
        if suggestions_by_issue
        else [],
        checks=[
            Check(enabled=True, slug=CheckType.SUPERVISOR_TRUST),
            Check(enabled=True, slug=CheckType.FREE_SPACE),
        ],
    )

    if suggestions_by_issue:

        async def mock_suggestions_for_issue(uuid: UUID) -> list[Suggestion]:
            """Mock of suggestions for issue api."""
            return suggestions_by_issue.get(uuid, [])

        supervisor_client.resolution.suggestions_for_issue.side_effect = (
            mock_suggestions_for_issue
        )
        supervisor_client.resolution.apply_suggestion.side_effect = suggestion_result


def assert_repair_in_list(
    issues: list[dict[str, Any]], unhealthy: bool, reason: str
) -> None:
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
    *,
    reference: str | None = None,
    placeholders: dict[str, str] | None = None,
) -> None:
    """Assert repair for unhealthy/unsupported in list."""
    if reference:
        placeholders = (placeholders or {}) | {"reference": reference}
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
        "translation_placeholders": placeholders,
    } in issues


@pytest.mark.usefixtures("all_setup_requests")
async def test_unhealthy_issues(
    hass: HomeAssistant,
    supervisor_client: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test issues added for unhealthy systems."""
    mock_resolution_info(
        supervisor_client, unhealthy=[UnhealthyReason.DOCKER, UnhealthyReason.SETUP]
    )

    result = await async_setup_component(hass, "hassio", {})
    assert result

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 2
    assert_repair_in_list(msg["result"]["issues"], unhealthy=True, reason="docker")
    assert_repair_in_list(msg["result"]["issues"], unhealthy=True, reason="setup")


@pytest.mark.usefixtures("all_setup_requests")
async def test_unsupported_issues(
    hass: HomeAssistant,
    supervisor_client: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test issues added for unsupported systems."""
    mock_resolution_info(
        supervisor_client,
        unsupported=[UnsupportedReason.CONTENT_TRUST, UnsupportedReason.OS],
    )

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


@pytest.mark.usefixtures("all_setup_requests")
async def test_unhealthy_issues_add_remove(
    hass: HomeAssistant,
    supervisor_client: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test unhealthy issues added and removed from dispatches."""
    mock_resolution_info(supervisor_client)

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


@pytest.mark.usefixtures("all_setup_requests")
async def test_unsupported_issues_add_remove(
    hass: HomeAssistant,
    supervisor_client: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test unsupported issues added and removed from dispatches."""
    mock_resolution_info(supervisor_client)

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


@pytest.mark.usefixtures("all_setup_requests")
async def test_reset_issues_supervisor_restart(
    hass: HomeAssistant,
    supervisor_client: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """All issues reset on supervisor restart."""
    mock_resolution_info(
        supervisor_client,
        unsupported=[UnsupportedReason.OS],
        unhealthy=[UnhealthyReason.DOCKER],
        issues=[
            Issue(
                type=IssueType.REBOOT_REQUIRED,
                context=ContextType.SYSTEM,
                reference=None,
                uuid=(uuid := uuid4()),
            )
        ],
        suggestions_by_issue={
            uuid: [
                Suggestion(
                    SuggestionType.EXECUTE_REBOOT,
                    context=ContextType.SYSTEM,
                    reference=None,
                    uuid=uuid4(),
                    auto=False,
                )
            ]
        },
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
        uuid=uuid.hex,
        context="system",
        type_="reboot_required",
        fixable=True,
        reference=None,
    )

    mock_resolution_info(supervisor_client)
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


@pytest.mark.usefixtures("all_setup_requests")
async def test_reasons_added_and_removed(
    hass: HomeAssistant,
    supervisor_client: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test an unsupported/unhealthy reasons being added and removed at same time."""
    mock_resolution_info(
        supervisor_client,
        unsupported=[UnsupportedReason.OS],
        unhealthy=[UnhealthyReason.DOCKER],
    )

    result = await async_setup_component(hass, "hassio", {})
    assert result

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 2
    assert_repair_in_list(msg["result"]["issues"], unhealthy=True, reason="docker")
    assert_repair_in_list(msg["result"]["issues"], unhealthy=False, reason="os")

    mock_resolution_info(
        supervisor_client,
        unsupported=[UnsupportedReason.CONTENT_TRUST],
        unhealthy=[UnhealthyReason.SETUP],
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


@pytest.mark.usefixtures("all_setup_requests")
async def test_ignored_unsupported_skipped(
    hass: HomeAssistant,
    supervisor_client: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Unsupported reasons which have an identical unhealthy reason are ignored."""
    mock_resolution_info(
        supervisor_client,
        unsupported=[UnsupportedReason.PRIVILEGED],
        unhealthy=[UnhealthyReason.PRIVILEGED],
    )

    result = await async_setup_component(hass, "hassio", {})
    assert result

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 1
    assert_repair_in_list(msg["result"]["issues"], unhealthy=True, reason="privileged")


@pytest.mark.usefixtures("all_setup_requests")
async def test_new_unsupported_unhealthy_reason(
    hass: HomeAssistant,
    supervisor_client: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """New unsupported/unhealthy reasons result in a generic repair until next core update."""
    mock_resolution_info(
        supervisor_client,
        unsupported=["fake_unsupported"],
        unhealthy=["fake_unhealthy"],
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


@pytest.mark.usefixtures("all_setup_requests")
async def test_supervisor_issues(
    hass: HomeAssistant,
    supervisor_client: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test repairs added for supervisor issue."""
    mock_resolution_info(
        supervisor_client,
        issues=[
            Issue(
                type=IssueType.DETACHED_ADDON_MISSING,
                context=ContextType.ADDON,
                reference="test",
                uuid=(uuid_issue1 := uuid4()),
            ),
            Issue(
                type=IssueType.MULTIPLE_DATA_DISKS,
                context=ContextType.SYSTEM,
                reference="/dev/sda1",
                uuid=(uuid_issue2 := uuid4()),
            ),
            Issue(
                type="should_not_be_repair",
                context=ContextType.OS,
                reference=None,
                uuid=uuid4(),
            ),
        ],
        suggestions_by_issue={
            uuid_issue2: [
                Suggestion(
                    type=SuggestionType.RENAME_DATA_DISK,
                    context=ContextType.SYSTEM,
                    reference="/dev/sda1",
                    uuid=uuid4(),
                    auto=False,
                )
            ]
        },
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
        uuid=uuid_issue1.hex,
        context="addon",
        type_="detached_addon_missing",
        fixable=False,
        reference="test",
        placeholders={"addon_url": "/hassio/addon/test", "addon": "test"},
    )
    assert_issue_repair_in_list(
        msg["result"]["issues"],
        uuid=uuid_issue2.hex,
        context="system",
        type_="multiple_data_disks",
        fixable=True,
        reference="/dev/sda1",
    )


@pytest.mark.usefixtures("all_setup_requests")
async def test_supervisor_issues_initial_failure(
    hass: HomeAssistant,
    supervisor_client: AsyncMock,
    resolution_info: AsyncMock,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test issues manager retries after initial update failure."""
    mock_resolution_info(
        supervisor_client,
        unsupported=[],
        unhealthy=[],
        issues=[
            Issue(
                type=IssueType.REBOOT_REQUIRED,
                context=ContextType.SYSTEM,
                reference=None,
                uuid=(uuid := uuid4()),
            )
        ],
        suggestions_by_issue={
            uuid: [
                Suggestion(
                    SuggestionType.EXECUTE_REBOOT,
                    context=ContextType.SYSTEM,
                    reference=None,
                    uuid=uuid4(),
                    auto=False,
                )
            ]
        },
    )
    resolution_info.side_effect = [
        SupervisorBadRequestError("System is not ready with state: setup"),
        resolution_info.return_value,
    ]

    with patch("homeassistant.components.hassio.issues.REQUEST_REFRESH_DELAY", new=0.1):
        result = await async_setup_component(hass, "hassio", {})
        await hass.async_block_till_done()
        assert result

        client = await hass_ws_client(hass)

        await client.send_json({"id": 1, "type": "repairs/list_issues"})
        msg = await client.receive_json()
        assert msg["success"]
        assert len(msg["result"]["issues"]) == 0

        freezer.tick(timedelta(milliseconds=200))
        await hass.async_block_till_done()
        await client.send_json({"id": 2, "type": "repairs/list_issues"})
        msg = await client.receive_json()
        assert msg["success"]
        assert len(msg["result"]["issues"]) == 1


@pytest.mark.usefixtures("all_setup_requests")
async def test_supervisor_issues_add_remove(
    hass: HomeAssistant,
    supervisor_client: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test supervisor issues added and removed from dispatches."""
    mock_resolution_info(supervisor_client)

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
                    "uuid": (issue_uuid := uuid4().hex),
                    "type": "reboot_required",
                    "context": "system",
                    "reference": None,
                    "suggestions": [
                        {
                            "uuid": uuid4().hex,
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

    await client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 1
    assert_issue_repair_in_list(
        msg["result"]["issues"],
        uuid=issue_uuid,
        context="system",
        type_="reboot_required",
        fixable=True,
        reference=None,
    )

    await client.send_json(
        {
            "id": 3,
            "type": "supervisor/event",
            "data": {
                "event": "issue_removed",
                "data": {
                    "uuid": issue_uuid,
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

    await client.send_json({"id": 4, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"issues": []}


@pytest.mark.usefixtures("all_setup_requests")
async def test_supervisor_issues_suggestions_fail(
    hass: HomeAssistant,
    supervisor_client: AsyncMock,
    resolution_suggestions_for_issue: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test failing to get suggestions for issue skips it."""
    mock_resolution_info(
        supervisor_client,
        issues=[
            Issue(
                type=IssueType.REBOOT_REQUIRED,
                context=ContextType.SYSTEM,
                reference=None,
                uuid=uuid4(),
            )
        ],
    )
    resolution_suggestions_for_issue.side_effect = SupervisorTimeoutError

    result = await async_setup_component(hass, "hassio", {})
    assert result

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 0


@pytest.mark.usefixtures("all_setup_requests")
async def test_supervisor_remove_missing_issue_without_error(
    hass: HomeAssistant,
    supervisor_client: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test HA skips message to remove issue that it didn't know about (sync issue)."""
    mock_resolution_info(supervisor_client)

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


@pytest.mark.usefixtures("all_setup_requests")
async def test_system_is_not_ready(
    hass: HomeAssistant,
    resolution_info: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Ensure hassio starts despite error."""
    resolution_info.side_effect = SupervisorBadRequestError(
        "System is not ready with state: setup"
    )

    assert await async_setup_component(hass, "hassio", {})
    assert "Failed to update supervisor issues" in caplog.text


@pytest.mark.parametrize(
    "all_setup_requests", [{"include_addons": True}], indirect=True
)
@pytest.mark.usefixtures("all_setup_requests")
async def test_supervisor_issues_detached_addon_missing(
    hass: HomeAssistant,
    supervisor_client: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test supervisor issue for detached addon due to missing repository."""
    mock_resolution_info(supervisor_client)

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
                    "uuid": (issue_uuid := uuid4().hex),
                    "type": "detached_addon_missing",
                    "context": "addon",
                    "reference": "test",
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
        uuid=issue_uuid,
        context="addon",
        type_="detached_addon_missing",
        fixable=False,
        placeholders={
            "reference": "test",
            "addon": "test",
            "addon_url": "/hassio/addon/test",
        },
    )
