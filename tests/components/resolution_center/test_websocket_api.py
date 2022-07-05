"""Test the resolution center websocket API."""
from homeassistant.components.resolution_center import async_create_issue
from homeassistant.components.resolution_center.const import DOMAIN
from homeassistant.const import MAJOR_VERSION, MINOR_VERSION, PATCH_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_dismiss_issue(hass: HomeAssistant, hass_ws_client) -> None:
    """Test we can dismiss an issue."""
    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    issues = [
        {
            "breaks_in_ha_version": "2022.9",
            "domain": "test",
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

    await client.send_json(
        {
            "id": 2,
            "type": "resolution_center/dismiss_issue",
            "domain": "test",
            "issue_id": "no_such_issue",
        }
    )
    msg = await client.receive_json()
    assert not msg["success"]

    await client.send_json(
        {
            "id": 3,
            "type": "resolution_center/dismiss_issue",
            "domain": "test",
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
                dismissed=True,
                dismissed_version_major=MAJOR_VERSION,
                dismissed_version_minor=MINOR_VERSION,
                dismissed_version_patch=PATCH_VERSION,
            )
            for issue in issues
        ]
    }


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
                dismissed=False,
                dismissed_version_major=None,
                dismissed_version_minor=None,
                dismissed_version_patch=None,
            )
            for issue in issues
        ]
    }
