"""Test the resolution center websocket API."""
from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant.components.resolution_center import (
    async_create_issue,
    async_delete_issue,
)
from homeassistant.components.resolution_center.const import DOMAIN
from homeassistant.components.resolution_center.resolution_center import (
    async_dismiss_issue,
    async_process_resolution_center_platforms,
)
from homeassistant.const import MAJOR_VERSION, MINOR_VERSION, PATCH_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import mock_platform


async def test_create_update_issue(hass: HomeAssistant, hass_ws_client) -> None:
    """Test creating and updating issues."""
    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "resolution_center/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {"issues": []}

    issues = [
        {
            "breaks_in_ha_version": "2022.9",
            "description_i18n_key": "abc_123",
            "domain": "test",
            "issue_id": "issue_1",
            "fix_label_i18n_key": "def_456",
            "is_fixable": True,
            "learn_more_url": "https://theuselessweb.com",
            "placeholders_i18n_keys": {"abc": "123"},
            "severity": "error",
            "title_i18n_key": "veryverybad",
        },
        {
            "breaks_in_ha_version": "2022.8",
            "description_i18n_key": "def_456",
            "domain": "test",
            "issue_id": "issue_2",
            "fix_label_i18n_key": "abc_123",
            "is_fixable": False,
            "learn_more_url": "https://theuselessweb.com/abc",
            "placeholders_i18n_keys": {"def": "456"},
            "severity": "other",
            "title_i18n_key": "even_worse",
        },
    ]

    for issue in issues:
        async_create_issue(
            hass,
            issue["domain"],
            issue["issue_id"],
            breaks_in_ha_version=issue["breaks_in_ha_version"],
            description_i18n_key=issue["description_i18n_key"],
            fix_label_i18n_key=issue["fix_label_i18n_key"],
            is_fixable=issue["is_fixable"],
            learn_more_url=issue["learn_more_url"],
            placeholders_i18n_keys=issue["placeholders_i18n_keys"],
            severity=issue["severity"],
            title_i18n_key=issue["title_i18n_key"],
        )

    await client.send_json({"id": 2, "type": "resolution_center/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            dict(
                issue,
                dismissed=False,
                dismissed_version_major=None,
                dismissed_version_minor=None,
                dismissed_version_patch=None,
            )
            for issue in issues
        ]
    }

    # Update an issue
    async_create_issue(
        hass,
        issues[0]["domain"],
        issues[0]["issue_id"],
        breaks_in_ha_version=issues[0]["breaks_in_ha_version"],
        description_i18n_key=issues[0]["description_i18n_key"],
        fix_label_i18n_key=issues[0]["fix_label_i18n_key"],
        is_fixable=issues[0]["is_fixable"],
        learn_more_url="blablabla",
        placeholders_i18n_keys=issues[0]["placeholders_i18n_keys"],
        severity=issues[0]["severity"],
        title_i18n_key=issues[0]["title_i18n_key"],
    )

    await client.send_json({"id": 3, "type": "resolution_center/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"]["issues"][0] == dict(
        issues[0],
        dismissed=False,
        dismissed_version_major=None,
        dismissed_version_minor=None,
        dismissed_version_patch=None,
        learn_more_url="blablabla",
    )


async def test_dismiss_issue(hass: HomeAssistant, hass_ws_client) -> None:
    """Test dismissing issues."""
    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "resolution_center/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {"issues": []}

    issues = [
        {
            "breaks_in_ha_version": "2022.9",
            "description_i18n_key": "abc_123",
            "domain": "test",
            "issue_id": "issue_1",
            "fix_label_i18n_key": "def_456",
            "is_fixable": True,
            "learn_more_url": "https://theuselessweb.com",
            "placeholders_i18n_keys": {"abc": "123"},
            "severity": "error",
            "title_i18n_key": "veryverybad",
        },
    ]

    for issue in issues:
        async_create_issue(
            hass,
            issue["domain"],
            issue["issue_id"],
            breaks_in_ha_version=issue["breaks_in_ha_version"],
            description_i18n_key=issue["description_i18n_key"],
            fix_label_i18n_key=issue["fix_label_i18n_key"],
            is_fixable=issue["is_fixable"],
            learn_more_url=issue["learn_more_url"],
            placeholders_i18n_keys=issue["placeholders_i18n_keys"],
            severity=issue["severity"],
            title_i18n_key=issue["title_i18n_key"],
        )

    await client.send_json({"id": 2, "type": "resolution_center/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            dict(
                issue,
                dismissed=False,
                dismissed_version_major=None,
                dismissed_version_minor=None,
                dismissed_version_patch=None,
            )
            for issue in issues
        ]
    }

    # Dismiss a non-existing issue
    with pytest.raises(KeyError):
        async_dismiss_issue(hass, issues[0]["domain"], "no_such_issue")

    await client.send_json({"id": 3, "type": "resolution_center/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            dict(
                issue,
                dismissed=False,
                dismissed_version_major=None,
                dismissed_version_minor=None,
                dismissed_version_patch=None,
            )
            for issue in issues
        ]
    }

    # Dismiss an existing issue
    async_dismiss_issue(hass, issues[0]["domain"], issues[0]["issue_id"])

    await client.send_json({"id": 4, "type": "resolution_center/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            dict(
                issue,
                dismissed=True,
                dismissed_version_major=MAJOR_VERSION,
                dismissed_version_minor=MINOR_VERSION,
                dismissed_version_patch=PATCH_VERSION,
            )
            for issue in issues
        ]
    }

    # Dismiss the same issue again
    async_dismiss_issue(hass, issues[0]["domain"], issues[0]["issue_id"])

    await client.send_json({"id": 5, "type": "resolution_center/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            dict(
                issue,
                dismissed=True,
                dismissed_version_major=MAJOR_VERSION,
                dismissed_version_minor=MINOR_VERSION,
                dismissed_version_patch=PATCH_VERSION,
            )
            for issue in issues
        ]
    }

    # Update a dismissed issue
    async_create_issue(
        hass,
        issues[0]["domain"],
        issues[0]["issue_id"],
        breaks_in_ha_version=issues[0]["breaks_in_ha_version"],
        description_i18n_key=issues[0]["description_i18n_key"],
        fix_label_i18n_key=issues[0]["fix_label_i18n_key"],
        is_fixable=issues[0]["is_fixable"],
        learn_more_url="blablabla",
        placeholders_i18n_keys=issues[0]["placeholders_i18n_keys"],
        severity=issues[0]["severity"],
        title_i18n_key=issues[0]["title_i18n_key"],
    )

    await client.send_json({"id": 6, "type": "resolution_center/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"]["issues"][0] == dict(
        issues[0],
        dismissed=True,
        dismissed_version_major=MAJOR_VERSION,
        dismissed_version_minor=MINOR_VERSION,
        dismissed_version_patch=PATCH_VERSION,
        learn_more_url="blablabla",
    )


async def test_delete_issue(hass: HomeAssistant, hass_ws_client) -> None:
    """Test we can delete an issue."""
    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    issues = [
        {
            "breaks_in_ha_version": "2022.9",
            "description_i18n_key": "abc_123",
            "domain": "fake_integration",
            "issue_id": "issue_1",
            "fix_label_i18n_key": "def_456",
            "is_fixable": True,
            "learn_more_url": "https://theuselessweb.com",
            "placeholders_i18n_keys": {"abc": "123"},
            "severity": "error",
            "title_i18n_key": "veryverybad",
        },
    ]

    for issue in issues:
        async_create_issue(
            hass,
            issue["domain"],
            issue["issue_id"],
            breaks_in_ha_version=issue["breaks_in_ha_version"],
            description_i18n_key=issue["description_i18n_key"],
            fix_label_i18n_key=issue["fix_label_i18n_key"],
            is_fixable=issue["is_fixable"],
            learn_more_url=issue["learn_more_url"],
            placeholders_i18n_keys=issue["placeholders_i18n_keys"],
            severity=issue["severity"],
            title_i18n_key=issue["title_i18n_key"],
        )

    await client.send_json({"id": 1, "type": "resolution_center/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            dict(
                issue,
                dismissed=False,
                dismissed_version_major=None,
                dismissed_version_minor=None,
                dismissed_version_patch=None,
            )
            for issue in issues
        ]
    }

    # Delete a non-existing issue
    async_delete_issue(hass, issues[0]["domain"], "no_such_issue")

    await client.send_json({"id": 2, "type": "resolution_center/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            dict(
                issue,
                dismissed=False,
                dismissed_version_major=None,
                dismissed_version_minor=None,
                dismissed_version_patch=None,
            )
            for issue in issues
        ]
    }

    # Delete an existing issue
    async_delete_issue(hass, issues[0]["domain"], issues[0]["issue_id"])

    await client.send_json({"id": 3, "type": "resolution_center/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {"issues": []}

    # Delete the same issue again
    async_delete_issue(hass, issues[0]["domain"], issues[0]["issue_id"])

    await client.send_json({"id": 4, "type": "resolution_center/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {"issues": []}


async def test_non_compliant_platform(hass: HomeAssistant, hass_ws_client) -> None:
    """Test non-compliant platforms are not registered."""

    hass.config.components.add("fake_integration")
    hass.config.components.add("integration_without_diagnostics")
    mock_platform(
        hass,
        "fake_integration.resolution_center",
        Mock(async_fix_issue=AsyncMock(return_value=True)),
    )
    mock_platform(
        hass,
        "integration_without_diagnostics.resolution_center",
        Mock(spec=[]),
    )
    assert await async_setup_component(hass, DOMAIN, {})

    await async_process_resolution_center_platforms(hass)

    assert list(hass.data[DOMAIN]["resolution_center_platforms"].keys()) == [
        "fake_integration"
    ]
