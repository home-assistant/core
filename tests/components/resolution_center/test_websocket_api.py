"""Test the resolution center websocket API."""
from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant.components.resolution_center import async_create_issue
from homeassistant.components.resolution_center.const import DOMAIN
from homeassistant.const import MAJOR_VERSION, MINOR_VERSION, PATCH_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import mock_platform


@pytest.fixture(autouse=True)
async def mock_resolution_center_integration(hass):
    """Mock a resolution_center integration."""
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


async def test_dismiss_issue(hass: HomeAssistant, hass_ws_client) -> None:
    """Test we can dismiss an issue."""
    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

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


async def test_fix_issue(hass: HomeAssistant, hass_ws_client) -> None:
    """Test we can fix an issue."""
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

    await client.send_json(
        {
            "id": 2,
            "type": "resolution_center/fix_issue",
            "domain": "test",
            "issue_id": "no_such_issue",
        }
    )
    msg = await client.receive_json()
    assert not msg["success"]

    await client.send_json(
        {
            "id": 3,
            "type": "resolution_center/fix_issue",
            "domain": "fake_integration",
            "issue_id": "issue_1",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]  # TODO: Add a test platform

    await client.send_json({"id": 4, "type": "resolution_center/list_issues"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {"issues": []}


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
