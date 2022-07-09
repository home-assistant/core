"""Test the resolution center websocket API."""
import pytest

from homeassistant.components.resolution_center import (
    async_create_issue,
    async_delete_issue,
)
from homeassistant.components.resolution_center.const import DOMAIN
from homeassistant.components.resolution_center.issue_handler import async_dismiss_issue
from homeassistant.const import __version__ as ha_version
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


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
            "breaks_in_ha_version": "2022.9.0dev0",
            "domain": "test",
            "issue_id": "issue_1",
            "learn_more_url": "https://theuselessweb.com",
            "severity": "error",
            "translation_key": "abc_123",
            "translation_placeholders": {"abc": "123"},
        },
        {
            "breaks_in_ha_version": "2022.8",
            "domain": "test",
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
                dismissed=False,
                dismissed_version=None,
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
        learn_more_url="blablabla",
        severity=issues[0]["severity"],
        translation_key=issues[0]["translation_key"],
        translation_placeholders=issues[0]["translation_placeholders"],
    )

    await client.send_json({"id": 3, "type": "resolution_center/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"]["issues"][0] == dict(
        issues[0],
        dismissed=False,
        dismissed_version=None,
        learn_more_url="blablabla",
    )


@pytest.mark.parametrize("ha_version", ("2022.9.cat", "In the future: 2023.1.1"))
async def test_create_issue_invalid_version(
    hass: HomeAssistant, hass_ws_client, ha_version
) -> None:
    """Test creating an issue with invalid breaks in version."""
    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    issue = {
        "breaks_in_ha_version": ha_version,
        "domain": "test",
        "issue_id": "issue_1",
        "learn_more_url": "https://theuselessweb.com",
        "severity": "error",
        "translation_key": "abc_123",
        "translation_placeholders": {"abc": "123"},
    }

    with pytest.raises(Exception):
        async_create_issue(
            hass,
            issue["domain"],
            issue["issue_id"],
            breaks_in_ha_version=issue["breaks_in_ha_version"],
            learn_more_url=issue["learn_more_url"],
            severity=issue["severity"],
            translation_key=issue["translation_key"],
            translation_placeholders=issue["translation_placeholders"],
        )

    await client.send_json({"id": 1, "type": "resolution_center/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {"issues": []}


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
            "domain": "test",
            "issue_id": "issue_1",
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
                dismissed=False,
                dismissed_version=None,
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
                dismissed_version=None,
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
                dismissed_version=ha_version,
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
                dismissed_version=ha_version,
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
        learn_more_url="blablabla",
        severity=issues[0]["severity"],
        translation_key=issues[0]["translation_key"],
        translation_placeholders=issues[0]["translation_placeholders"],
    )

    await client.send_json({"id": 6, "type": "resolution_center/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"]["issues"][0] == dict(
        issues[0],
        dismissed=True,
        dismissed_version=ha_version,
        learn_more_url="blablabla",
    )


async def test_delete_issue(hass: HomeAssistant, hass_ws_client) -> None:
    """Test we can delete an issue."""
    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    issues = [
        {
            "breaks_in_ha_version": "2022.9",
            "domain": "fake_integration",
            "issue_id": "issue_1",
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
            learn_more_url=issue["learn_more_url"],
            severity=issue["severity"],
            translation_key=issue["translation_key"],
            translation_placeholders=issue["translation_placeholders"],
        )

    await client.send_json({"id": 1, "type": "resolution_center/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            dict(
                issue,
                dismissed=False,
                dismissed_version=None,
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
                dismissed_version=None,
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
