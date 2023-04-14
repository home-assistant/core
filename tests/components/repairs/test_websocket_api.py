"""Test the repairs websocket API."""
from __future__ import annotations

from http import HTTPStatus
from typing import Any
from unittest.mock import ANY, AsyncMock, Mock

import pytest
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.components.repairs.const import DOMAIN
from homeassistant.const import __version__ as ha_version
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockUser, mock_platform
from tests.typing import ClientSessionGenerator, WebSocketGenerator

DEFAULT_ISSUES = [
    {
        "breaks_in_ha_version": "2022.9",
        "domain": "fake_integration",
        "issue_id": "issue_1",
        "is_fixable": True,
        "learn_more_url": "https://theuselessweb.com",
        "severity": "error",
        "translation_key": "abc_123",
        "translation_placeholders": {"abc": "123"},
    }
]


async def create_issues(hass, ws_client, issues=None):
    """Create issues."""

    def api_issue(issue):
        excluded_keys = ("data",)
        return dict(
            {key: issue[key] for key in issue if key not in excluded_keys},
            created=ANY,
            dismissed_version=None,
            ignored=False,
            issue_domain=None,
        )

    if issues is None:
        issues = DEFAULT_ISSUES

    for issue in issues:
        ir.async_create_issue(
            hass,
            issue["domain"],
            issue["issue_id"],
            breaks_in_ha_version=issue["breaks_in_ha_version"],
            data=issue.get("data"),
            is_fixable=issue["is_fixable"],
            is_persistent=False,
            learn_more_url=issue["learn_more_url"],
            severity=issue["severity"],
            translation_key=issue["translation_key"],
            translation_placeholders=issue["translation_placeholders"],
        )

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert msg["result"] == {"issues": [api_issue(issue) for issue in issues]}

    return issues


EXPECTED_DATA = {
    "issue_1": None,
    "issue_2": {"blah": "bleh"},
    "abort_issue1": None,
}


class MockFixFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""

        assert self.issue_id in EXPECTED_DATA
        assert self.data == EXPECTED_DATA[self.issue_id]

        return await self.async_step_custom_step()

    async def async_step_custom_step(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle a custom_step step of a fix flow."""
        if user_input is not None:
            return self.async_create_entry(data={})

        return self.async_show_form(step_id="custom_step", data_schema=vol.Schema({}))


class MockFixFlowAbort(RepairsFlow):
    """Handler for an issue fixing flow that aborts."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        return self.async_abort(reason="not_given")


@pytest.fixture(autouse=True)
async def mock_repairs_integration(hass):
    """Mock a repairs integration."""
    hass.config.components.add("fake_integration")

    def async_create_fix_flow(hass, issue_id, data):
        assert issue_id in EXPECTED_DATA
        assert data == EXPECTED_DATA[issue_id]

        if issue_id == "abort_issue1":
            return MockFixFlowAbort()
        return MockFixFlow()

    mock_platform(
        hass,
        "fake_integration.repairs",
        Mock(async_create_fix_flow=AsyncMock(wraps=async_create_fix_flow)),
    )
    mock_platform(
        hass,
        "integration_without_repairs.repairs",
        Mock(spec=[]),
    )


async def test_dismiss_issue(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test we can dismiss an issue."""
    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    issues = await create_issues(hass, client)

    await client.send_json(
        {
            "id": 2,
            "type": "repairs/ignore_issue",
            "domain": "fake_integration",
            "issue_id": "no_such_issue",
            "ignore": True,
        }
    )
    msg = await client.receive_json()
    assert not msg["success"]

    await client.send_json(
        {
            "id": 3,
            "type": "repairs/ignore_issue",
            "domain": "fake_integration",
            "issue_id": "issue_1",
            "ignore": True,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    await client.send_json({"id": 4, "type": "repairs/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            dict(
                issue,
                created=ANY,
                dismissed_version=ha_version,
                ignored=True,
                issue_domain=None,
            )
            for issue in issues
        ]
    }

    await client.send_json(
        {
            "id": 5,
            "type": "repairs/ignore_issue",
            "domain": "fake_integration",
            "issue_id": "issue_1",
            "ignore": False,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    await client.send_json({"id": 6, "type": "repairs/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            dict(
                issue,
                created=ANY,
                dismissed_version=None,
                ignored=False,
                issue_domain=None,
            )
            for issue in issues
        ]
    }


async def test_fix_non_existing_issue(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test trying to fix an issue that doesn't exist."""
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, DOMAIN, {})

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    issues = await create_issues(hass, ws_client)

    url = "/api/repairs/issues/fix"
    resp = await client.post(
        url, json={"handler": "no_such_integration", "issue_id": "no_such_issue"}
    )

    assert resp.status != HTTPStatus.OK

    url = "/api/repairs/issues/fix"
    resp = await client.post(
        url, json={"handler": "fake_integration", "issue_id": "no_such_issue"}
    )

    assert resp.status != HTTPStatus.OK

    await ws_client.send_json({"id": 3, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            dict(
                issue,
                created=ANY,
                dismissed_version=None,
                ignored=False,
                issue_domain=None,
            )
            for issue in issues
        ]
    }


@pytest.mark.parametrize(
    ("domain", "step", "description_placeholders"),
    (
        ("fake_integration", "custom_step", None),
        ("fake_integration_default_handler", "confirm", {"abc": "123"}),
    ),
)
async def test_fix_issue(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    domain,
    step,
    description_placeholders,
) -> None:
    """Test we can fix an issue."""
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, DOMAIN, {})

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    issues = [
        {
            **DEFAULT_ISSUES[0],
            "data": {"blah": "bleh"},
            "domain": domain,
            "issue_id": "issue_2",
        }
    ]
    await create_issues(hass, ws_client, issues=issues)

    url = "/api/repairs/issues/fix"
    resp = await client.post(url, json={"handler": domain, "issue_id": "issue_2"})

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "data_schema": [],
        "description_placeholders": description_placeholders,
        "errors": None,
        "flow_id": ANY,
        "handler": domain,
        "last_step": None,
        "step_id": step,
        "type": "form",
    }

    url = f"/api/repairs/issues/fix/{flow_id}"
    # Test we can get the status of the flow
    resp2 = await client.get(url)

    assert resp2.status == HTTPStatus.OK
    data2 = await resp2.json()

    assert data == data2

    resp = await client.post(url)

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "description": None,
        "description_placeholders": None,
        "flow_id": flow_id,
        "handler": domain,
        "type": "create_entry",
        "version": 1,
    }

    await ws_client.send_json({"id": 4, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert msg["result"] == {"issues": []}


async def test_fix_issue_unauth(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, hass_admin_user: MockUser
) -> None:
    """Test we can't query the result if not authorized."""
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, DOMAIN, {})

    hass_admin_user.groups = []

    client = await hass_client()

    url = "/api/repairs/issues/fix"
    resp = await client.post(
        url, json={"handler": "fake_integration", "issue_id": "issue_1"}
    )

    assert resp.status == HTTPStatus.UNAUTHORIZED


async def test_get_progress_unauth(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: MockUser,
) -> None:
    """Test we can't fix an issue if not authorized."""
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, DOMAIN, {})

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await create_issues(hass, ws_client)

    url = "/api/repairs/issues/fix"
    resp = await client.post(
        url, json={"handler": "fake_integration", "issue_id": "issue_1"}
    )
    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    flow_id = data["flow_id"]

    hass_admin_user.groups = []

    url = f"/api/repairs/issues/fix/{flow_id}"
    # Test we can't get the status of the flow
    resp = await client.get(url)
    assert resp.status == HTTPStatus.UNAUTHORIZED


async def test_step_unauth(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: MockUser,
) -> None:
    """Test we can't fix an issue if not authorized."""
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, DOMAIN, {})

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await create_issues(hass, ws_client)

    url = "/api/repairs/issues/fix"
    resp = await client.post(
        url, json={"handler": "fake_integration", "issue_id": "issue_1"}
    )
    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    flow_id = data["flow_id"]

    hass_admin_user.groups = []

    url = f"/api/repairs/issues/fix/{flow_id}"
    # Test we can't get the status of the flow
    resp = await client.post(url)
    assert resp.status == HTTPStatus.UNAUTHORIZED


@pytest.mark.freeze_time("2022-07-19 07:53:05")
async def test_list_issues(
    hass: HomeAssistant, hass_storage: dict[str, Any], hass_ws_client
) -> None:
    """Test we can list issues."""

    # Add an inactive issue, this should not be exposed in the list
    hass_storage[ir.STORAGE_KEY] = {
        "version": ir.STORAGE_VERSION_MAJOR,
        "data": {
            "issues": [
                {
                    "created": "2022-07-19T09:41:13.746514+00:00",
                    "dismissed_version": None,
                    "domain": "test",
                    "is_persistent": False,
                    "issue_id": "issue_3_inactive",
                    "issue_domain": None,
                },
            ]
        },
    }

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
            "issue_domain": None,
            "learn_more_url": "https://theuselessweb.com",
            "severity": "error",
            "translation_key": "abc_123",
            "translation_placeholders": {"abc": "123"},
        },
        {
            "breaks_in_ha_version": "2022.8",
            "domain": "test",
            "is_fixable": False,
            "issue_id": "issue_2",
            "issue_domain": None,
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
            )
            for issue in issues
        ]
    }


async def test_fix_issue_aborted(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test we can fix an issue."""
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, DOMAIN, {})

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await create_issues(
        hass,
        ws_client,
        issues=[
            {
                **DEFAULT_ISSUES[0],
                "domain": "fake_integration",
                "issue_id": "abort_issue1",
            }
        ],
    )

    await ws_client.send_json({"id": 3, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) == 1

    first_issue = msg["result"]["issues"][0]

    assert first_issue["domain"] == "fake_integration"
    assert first_issue["issue_id"] == "abort_issue1"

    resp = await client.post(
        "/api/repairs/issues/fix",
        json={"handler": "fake_integration", "issue_id": "abort_issue1"},
    )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "type": "abort",
        "flow_id": flow_id,
        "handler": "fake_integration",
        "reason": "not_given",
        "description_placeholders": None,
        "result": None,
    }

    await ws_client.send_json({"id": 4, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) == 1
    assert msg["result"]["issues"][0] == first_issue
