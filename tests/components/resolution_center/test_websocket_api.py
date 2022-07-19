"""Test the resolution center websocket API."""
from __future__ import annotations

from http import HTTPStatus
from unittest.mock import ANY, AsyncMock, Mock

from freezegun import freeze_time
import pytest
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.resolution_center import (
    ResolutionCenterFlow,
    async_create_issue,
)
from homeassistant.components.resolution_center.const import DOMAIN
from homeassistant.const import __version__ as ha_version
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import mock_platform


async def create_issues(hass, ws_client):
    """Create issues."""
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
        async_create_issue(
            hass,
            issue["domain"],
            issue["issue_id"],
            breaks_in_ha_version=issue["breaks_in_ha_version"],
            is_fixable=issue["is_fixable"],
            learn_more_url=issue["learn_more_url"],
            severity=issue["severity"],
            translation_key=issue["translation_key"],
            translation_placeholders=issue["translation_placeholders"],
        )

    await ws_client.send_json({"id": 1, "type": "resolution_center/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            dict(
                issue,
                created=ANY,
                dismissed=False,
                dismissed_version=None,
            )
            for issue in issues
        ]
    }

    return issues


class MockFixFlow(ResolutionCenterFlow):
    """Handler for an issue fixing flow."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""

        return await (self.async_step_confirm())

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            return self.async_create_entry(title=None, data=None)

        return self.async_show_form(step_id="confirm", data_schema=vol.Schema({}))


@pytest.fixture(autouse=True)
async def mock_resolution_center_integration(hass):
    """Mock a resolution_center integration."""
    hass.config.components.add("fake_integration")
    hass.config.components.add("integration_without_diagnostics")

    def async_create_fix_flow(hass, issue_id):
        return MockFixFlow()

    mock_platform(
        hass,
        "fake_integration.resolution_center",
        Mock(async_create_fix_flow=AsyncMock(wraps=async_create_fix_flow)),
    )
    mock_platform(
        hass,
        "integration_without_diagnostics.resolution_center",
        Mock(spec=[]),
    )


async def test_dismiss_issue(hass: HomeAssistant, hass_ws_client) -> None:
    """Test we can dismiss an issue."""
    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    issues = await create_issues(hass, client)

    await client.send_json(
        {
            "id": 2,
            "type": "resolution_center/dismiss_issue",
            "domain": "fake_integration",
            "issue_id": "no_such_issue",
        }
    )
    msg = await client.receive_json()
    assert not msg["success"]

    await client.send_json(
        {
            "id": 3,
            "type": "resolution_center/dismiss_issue",
            "domain": "fake_integration",
            "issue_id": "issue_1",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    await client.send_json({"id": 4, "type": "resolution_center/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            dict(
                issue,
                created=ANY,
                dismissed=True,
                dismissed_version=ha_version,
            )
            for issue in issues
        ]
    }


async def test_fix_non_existing_issue(
    hass: HomeAssistant, hass_client, hass_ws_client
) -> None:
    """Test trying to fix an issue that doesn't exist."""
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, DOMAIN, {})

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    issues = await create_issues(hass, ws_client)

    url = "/api/resolution_center/issues/fix"
    resp = await client.post(
        url, json={"handler": "no_such_integration", "issue_id": "no_such_issue"}
    )

    assert resp.status != HTTPStatus.OK

    url = "/api/resolution_center/issues/fix"
    resp = await client.post(
        url, json={"handler": "fake_integration", "issue_id": "no_such_issue"}
    )

    assert resp.status != HTTPStatus.OK

    await ws_client.send_json({"id": 3, "type": "resolution_center/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            dict(
                issue,
                created=ANY,
                dismissed=False,
                dismissed_version=None,
            )
            for issue in issues
        ]
    }


async def test_fix_issue(hass: HomeAssistant, hass_client, hass_ws_client) -> None:
    """Test we can fix an issue."""
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, DOMAIN, {})

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await create_issues(hass, ws_client)

    url = "/api/resolution_center/issues/fix"
    resp = await client.post(
        url, json={"handler": "fake_integration", "issue_id": "issue_1"}
    )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "data_schema": [],
        "description_placeholders": None,
        "errors": None,
        "flow_id": ANY,
        "handler": "fake_integration",
        "last_step": None,
        "step_id": "confirm",
        "type": "form",
    }

    url = f"/api/resolution_center/issues/fix/{flow_id}"
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
        "handler": "fake_integration",
        "title": None,
        "type": "create_entry",
        "version": 1,
    }

    await ws_client.send_json({"id": 4, "type": "resolution_center/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert msg["result"] == {"issues": []}


async def test_fix_issue_unauth(
    hass: HomeAssistant, hass_client, hass_admin_user
) -> None:
    """Test we can't query the result if not authorized."""
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, DOMAIN, {})

    hass_admin_user.groups = []

    client = await hass_client()

    url = "/api/resolution_center/issues/fix"
    resp = await client.post(
        url, json={"handler": "fake_integration", "issue_id": "issue_1"}
    )

    assert resp.status == HTTPStatus.UNAUTHORIZED


async def test_get_progress_unauth(
    hass: HomeAssistant, hass_client, hass_ws_client, hass_admin_user
) -> None:
    """Test we can't fix an issue if not authorized."""
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, DOMAIN, {})

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await create_issues(hass, ws_client)

    url = "/api/resolution_center/issues/fix"
    resp = await client.post(
        url, json={"handler": "fake_integration", "issue_id": "issue_1"}
    )
    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    flow_id = data["flow_id"]

    hass_admin_user.groups = []

    url = f"/api/resolution_center/issues/fix/{flow_id}"
    # Test we can't get the status of the flow
    resp = await client.get(url)
    assert resp.status == HTTPStatus.UNAUTHORIZED


async def test_step_unauth(
    hass: HomeAssistant, hass_client, hass_ws_client, hass_admin_user
) -> None:
    """Test we can't fix an issue if not authorized."""
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, DOMAIN, {})

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await create_issues(hass, ws_client)

    url = "/api/resolution_center/issues/fix"
    resp = await client.post(
        url, json={"handler": "fake_integration", "issue_id": "issue_1"}
    )
    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    flow_id = data["flow_id"]

    hass_admin_user.groups = []

    url = f"/api/resolution_center/issues/fix/{flow_id}"
    # Test we can't get the status of the flow
    resp = await client.post(url)
    assert resp.status == HTTPStatus.UNAUTHORIZED


@freeze_time("2022-07-19 07:53:05")
async def test_list_issues(hass: HomeAssistant, hass_ws_client) -> None:
    """Test we can list issues."""
    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "resolution_center/list_issues"})
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
        {
            "breaks_in_ha_version": "2022.8",
            "domain": "test",
            "is_fixable": False,
            "issue_id": "issue_2",
            "learn_more_url": "https://theuselessweb.com/abc",
            "severity": "other",
            "translation_key": "even_worse",
            "translation_placeholders": {"def": "456"},
        },
    ]

    for issue in issues:
        async_create_issue(
            hass,
            issue["domain"],
            issue["issue_id"],
            breaks_in_ha_version=issue["breaks_in_ha_version"],
            is_fixable=issue["is_fixable"],
            learn_more_url=issue["learn_more_url"],
            severity=issue["severity"],
            translation_key=issue["translation_key"],
            translation_placeholders=issue["translation_placeholders"],
        )

    await client.send_json({"id": 2, "type": "resolution_center/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            dict(
                issue,
                created="2022-07-19T07:53:05+00:00",
                dismissed=False,
                dismissed_version=None,
            )
            for issue in issues
        ]
    }
