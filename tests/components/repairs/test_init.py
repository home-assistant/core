"""Test the repairs websocket API."""

from unittest.mock import AsyncMock, Mock

from awesomeversion.exceptions import AwesomeVersionStrategyException
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.repairs import repairs_flow_manager
from homeassistant.components.repairs.const import DOMAIN
from homeassistant.components.repairs.issue_handler import (
    RepairsFlowManager,
    async_process_repairs_platforms,
)
from homeassistant.const import __version__ as ha_version
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import mock_platform
from tests.typing import WebSocketGenerator


@pytest.mark.parametrize(
    "ignore_translations",
    [
        [
            "component.test.issues.even_worse.title",
            "component.test.issues.even_worse.description",
            "component.test.issues.abc_123.title",
        ]
    ],
)
@pytest.mark.freeze_time("2022-07-19 07:53:05")
async def test_create_update_issue(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test creating and updating issues."""
    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {"issues": []}

    issues = [
        {
            "breaks_in_ha_version": "2022.9.0dev0",
            "domain": "test",
            "issue_id": "issue_1",
            "is_fixable": True,
            "learn_more_url": "https://theuselessweb.com",
            "severity": "error",
            "translation_key": "abc_123",
            "translation_placeholders": {"abc": "123"},
        },
        {
            "breaks_in_ha_version": "2022.8",
            "domain": "test",
            "issue_id": "issue_2",
            "is_fixable": False,
            "learn_more_url": "https://theuselessweb.com/abc",
            "severity": "other",
            "translation_key": "even_worse",
            "translation_placeholders": {"def": "456"},
        },
    ]

    for issue in issues:
        ir.async_create_issue(
            hass,
            issue["domain"],
            issue["issue_id"],
            breaks_in_ha_version=issue["breaks_in_ha_version"],
            is_fixable=issue["is_fixable"],
            is_persistent=False,
            learn_more_url=issue["learn_more_url"],
            severity=issue["severity"],
            translation_key=issue["translation_key"],
            translation_placeholders=issue["translation_placeholders"],
        )

    await client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            dict(
                issue,
                created="2022-07-19T07:53:05+00:00",
                dismissed_version=None,
                ignored=False,
                issue_domain=None,
            )
            for issue in issues
        ]
    }

    # Update an issue
    ir.async_create_issue(
        hass,
        issues[0]["domain"],
        issues[0]["issue_id"],
        breaks_in_ha_version=issues[0]["breaks_in_ha_version"],
        is_fixable=issues[0]["is_fixable"],
        is_persistent=False,
        issue_domain="my_issue_domain",
        learn_more_url="blablabla",
        severity=issues[0]["severity"],
        translation_key=issues[0]["translation_key"],
        translation_placeholders=issues[0]["translation_placeholders"],
    )

    await client.send_json({"id": 3, "type": "repairs/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"]["issues"][0] == dict(
        issues[0],
        created="2022-07-19T07:53:05+00:00",
        dismissed_version=None,
        ignored=False,
        learn_more_url="blablabla",
        issue_domain="my_issue_domain",
    )


@pytest.mark.parametrize("ha_version", ["2022.9.cat", "In the future: 2023.1.1"])
async def test_create_issue_invalid_version(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, ha_version
) -> None:
    """Test creating an issue with invalid breaks in version."""
    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    issue = {
        "breaks_in_ha_version": ha_version,
        "domain": "test",
        "issue_id": "issue_1",
        "is_fixable": True,
        "learn_more_url": "https://theuselessweb.com",
        "severity": "error",
        "translation_key": "abc_123",
        "translation_placeholders": {"abc": "123"},
    }

    with pytest.raises(AwesomeVersionStrategyException):
        ir.async_create_issue(
            hass,
            issue["domain"],
            issue["issue_id"],
            breaks_in_ha_version=issue["breaks_in_ha_version"],
            is_fixable=issue["is_fixable"],
            is_persistent=False,
            learn_more_url=issue["learn_more_url"],
            severity=issue["severity"],
            translation_key=issue["translation_key"],
            translation_placeholders=issue["translation_placeholders"],
        )

    await client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {"issues": []}


@pytest.mark.parametrize(
    "ignore_translations",
    [
        [
            "component.test.issues.abc_123.title",
        ]
    ],
)
@pytest.mark.freeze_time("2022-07-19 07:53:05")
async def test_ignore_issue(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test ignoring issues."""
    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {"issues": []}

    issues = [
        {
            "breaks_in_ha_version": "2022.9",
            "domain": "test",
            "is_fixable": True,
            "issue_id": "issue_1",
            "learn_more_url": "https://theuselessweb.com",
            "severity": "error",
            "translation_key": "abc_123",
            "translation_placeholders": {"abc": "123"},
        },
    ]

    for issue in issues:
        ir.async_create_issue(
            hass,
            issue["domain"],
            issue["issue_id"],
            breaks_in_ha_version=issue["breaks_in_ha_version"],
            is_fixable=issue["is_fixable"],
            is_persistent=False,
            learn_more_url=issue["learn_more_url"],
            severity=issue["severity"],
            translation_key=issue["translation_key"],
            translation_placeholders=issue["translation_placeholders"],
        )

    await client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            dict(
                issue,
                created="2022-07-19T07:53:05+00:00",
                dismissed_version=None,
                ignored=False,
                issue_domain=None,
            )
            for issue in issues
        ]
    }

    # Ignore a non-existing issue
    with pytest.raises(KeyError):
        ir.async_ignore_issue(hass, issues[0]["domain"], "no_such_issue", True)

    await client.send_json({"id": 3, "type": "repairs/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            dict(
                issue,
                created="2022-07-19T07:53:05+00:00",
                dismissed_version=None,
                ignored=False,
                issue_domain=None,
            )
            for issue in issues
        ]
    }

    # Ignore an existing issue
    ir.async_ignore_issue(hass, issues[0]["domain"], issues[0]["issue_id"], True)

    await client.send_json({"id": 4, "type": "repairs/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            dict(
                issue,
                created="2022-07-19T07:53:05+00:00",
                dismissed_version=ha_version,
                ignored=True,
                issue_domain=None,
            )
            for issue in issues
        ]
    }

    # Ignore the same issue again
    ir.async_ignore_issue(hass, issues[0]["domain"], issues[0]["issue_id"], True)

    await client.send_json({"id": 5, "type": "repairs/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            dict(
                issue,
                created="2022-07-19T07:53:05+00:00",
                dismissed_version=ha_version,
                ignored=True,
                issue_domain=None,
            )
            for issue in issues
        ]
    }

    # Update an ignored issue
    ir.async_create_issue(
        hass,
        issues[0]["domain"],
        issues[0]["issue_id"],
        breaks_in_ha_version=issues[0]["breaks_in_ha_version"],
        is_fixable=issues[0]["is_fixable"],
        is_persistent=False,
        learn_more_url="blablabla",
        severity=issues[0]["severity"],
        translation_key=issues[0]["translation_key"],
        translation_placeholders=issues[0]["translation_placeholders"],
    )

    await client.send_json({"id": 6, "type": "repairs/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"]["issues"][0] == dict(
        issues[0],
        created="2022-07-19T07:53:05+00:00",
        dismissed_version=ha_version,
        ignored=True,
        learn_more_url="blablabla",
        issue_domain=None,
    )

    # Unignore the same issue
    ir.async_ignore_issue(hass, issues[0]["domain"], issues[0]["issue_id"], False)

    await client.send_json({"id": 7, "type": "repairs/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            dict(
                issue,
                created="2022-07-19T07:53:05+00:00",
                dismissed_version=None,
                ignored=False,
                learn_more_url="blablabla",
                issue_domain=None,
            )
            for issue in issues
        ]
    }


@pytest.mark.parametrize(
    "ignore_translations",
    ["component.fake_integration.issues.abc_123.title"],
)
@pytest.mark.freeze_time("2022-07-19 07:53:05")
async def test_delete_issue(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test we can delete an issue."""
    freezer.move_to("2022-07-19 07:53:05")
    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    issues = [
        {
            "breaks_in_ha_version": "2022.9",
            "domain": "fake_integration",
            "issue_id": "issue_1",
            "is_fixable": True,
            "learn_more_url": "https://theuselessweb.com",
            "severity": "error",
            "translation_key": "abc_123",
            "translation_placeholders": {"abc": "123"},
        },
    ]

    for issue in issues:
        ir.async_create_issue(
            hass,
            issue["domain"],
            issue["issue_id"],
            breaks_in_ha_version=issue["breaks_in_ha_version"],
            is_fixable=issue["is_fixable"],
            is_persistent=False,
            learn_more_url=issue["learn_more_url"],
            severity=issue["severity"],
            translation_key=issue["translation_key"],
            translation_placeholders=issue["translation_placeholders"],
        )

    await client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            dict(
                issue,
                created="2022-07-19T07:53:05+00:00",
                dismissed_version=None,
                ignored=False,
                issue_domain=None,
            )
            for issue in issues
        ]
    }

    # Delete a non-existing issue
    ir.async_delete_issue(hass, issues[0]["domain"], "no_such_issue")

    await client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            dict(
                issue,
                created="2022-07-19T07:53:05+00:00",
                dismissed_version=None,
                ignored=False,
                issue_domain=None,
            )
            for issue in issues
        ]
    }

    # Delete an existing issue
    ir.async_delete_issue(hass, issues[0]["domain"], issues[0]["issue_id"])

    await client.send_json({"id": 3, "type": "repairs/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {"issues": []}

    # Delete the same issue again
    ir.async_delete_issue(hass, issues[0]["domain"], issues[0]["issue_id"])

    await client.send_json({"id": 4, "type": "repairs/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {"issues": []}

    # Create the same issues again created timestamp should change
    freezer.move_to("2022-07-19 08:53:05")

    for issue in issues:
        ir.async_create_issue(
            hass,
            issue["domain"],
            issue["issue_id"],
            breaks_in_ha_version=issue["breaks_in_ha_version"],
            is_fixable=issue["is_fixable"],
            is_persistent=False,
            learn_more_url=issue["learn_more_url"],
            severity=issue["severity"],
            translation_key=issue["translation_key"],
            translation_placeholders=issue["translation_placeholders"],
        )

    await client.send_json({"id": 5, "type": "repairs/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            dict(
                issue,
                created="2022-07-19T08:53:05+00:00",
                dismissed_version=None,
                ignored=False,
                issue_domain=None,
            )
            for issue in issues
        ]
    }


@pytest.mark.no_fail_on_log_exception
async def test_non_compliant_platform(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test non-compliant platforms are not registered."""

    hass.config.components.add("fake_integration")
    hass.config.components.add("integration_without_repairs")
    mock_platform(
        hass,
        "fake_integration.repairs",
        Mock(async_create_fix_flow=AsyncMock(return_value=True)),
    )
    mock_platform(
        hass,
        "integration_without_repairs.repairs",
        Mock(spec=[]),
    )
    assert await async_setup_component(hass, DOMAIN, {})

    await async_process_repairs_platforms(hass)

    assert list(hass.data[DOMAIN]["platforms"].keys()) == ["fake_integration"]


@pytest.mark.parametrize(
    "ignore_translations",
    ["component.fake_integration.issues.abc_123.title"],
)
@pytest.mark.freeze_time("2022-07-21 08:22:00")
async def test_sync_methods(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test sync method for creating and deleting an issue."""

    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {"issues": []}

    def _create_issue() -> None:
        ir.create_issue(
            hass,
            "fake_integration",
            "sync_issue",
            breaks_in_ha_version="2022.9",
            is_fixable=True,
            is_persistent=False,
            learn_more_url="https://theuselessweb.com",
            severity=ir.IssueSeverity.ERROR,
            translation_key="abc_123",
            translation_placeholders={"abc": "123"},
        )

    await hass.async_add_executor_job(_create_issue)
    await client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            {
                "breaks_in_ha_version": "2022.9",
                "created": "2022-07-21T08:22:00+00:00",
                "dismissed_version": None,
                "domain": "fake_integration",
                "ignored": False,
                "is_fixable": True,
                "issue_id": "sync_issue",
                "issue_domain": None,
                "learn_more_url": "https://theuselessweb.com",
                "severity": "error",
                "translation_key": "abc_123",
                "translation_placeholders": {"abc": "123"},
            }
        ]
    }

    await hass.async_add_executor_job(
        ir.delete_issue, hass, "fake_integration", "sync_issue"
    )
    await client.send_json({"id": 3, "type": "repairs/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {"issues": []}


async def test_flow_manager_helper(hass: HomeAssistant) -> None:
    """Test accessing the repairs flow manager with the helper."""
    assert repairs_flow_manager(hass) is None

    assert await async_setup_component(hass, DOMAIN, {})

    flow_manager = repairs_flow_manager(hass)
    assert flow_manager is not None
    assert isinstance(flow_manager, RepairsFlowManager)
