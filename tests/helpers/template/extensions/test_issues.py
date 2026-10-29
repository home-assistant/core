"""Test issue template functions."""

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryDisabler
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from tests.helpers.template.helpers import assert_result_info, render_to_info


async def test_issues(hass: HomeAssistant, issue_registry: ir.IssueRegistry) -> None:
    """Test issues function."""
    # Test no issues
    info = render_to_info(hass, "{{ issues() }}")
    assert_result_info(info, {})
    assert info.rate_limit is None

    # Test persistent issue
    ir.async_create_issue(
        hass,
        "test",
        "issue 1",
        breaks_in_ha_version="2023.7",
        is_fixable=True,
        is_persistent=True,
        learn_more_url="https://theuselessweb.com",
        severity="error",
        translation_key="abc_1234",
        translation_placeholders={"abc": "123"},
    )
    await hass.async_block_till_done()
    created_issue = issue_registry.async_get_issue("test", "issue 1")
    info = render_to_info(hass, "{{ issues()['test', 'issue 1'] }}")
    assert_result_info(info, created_issue.to_json())
    assert info.rate_limit is None

    # Test fixed issue
    ir.async_delete_issue(hass, "test", "issue 1")
    await hass.async_block_till_done()
    info = render_to_info(hass, "{{ issues() }}")
    assert_result_info(info, {})
    assert info.rate_limit is None

    issue = ir.IssueEntry(
        active=False,
        breaks_in_ha_version="2025.12",
        config_entry_id=None,
        created=dt_util.utcnow(),
        data=None,
        dismissed_version=None,
        domain="test",
        is_fixable=False,
        is_persistent=False,
        issue_domain="test",
        issue_id="issue 2",
        learn_more_url=None,
        severity="warning",
        translation_key="abc_1234",
        translation_placeholders={"abc": "123"},
    )
    # Add non active issue
    issue_registry.issues[("test", "issue 2")] = issue
    # Test non active issue is omitted
    issue_entry = issue_registry.async_get_issue("test", "issue 2")
    assert issue_entry
    issue_2_created = issue_entry.created
    assert issue_entry and not issue_entry.active
    info = render_to_info(hass, "{{ issues() }}")
    assert_result_info(info, {})
    assert info.rate_limit is None

    # Load and activate the issue
    ir.async_create_issue(
        hass=hass,
        breaks_in_ha_version="2025.12",
        data=None,
        domain="test",
        is_fixable=False,
        is_persistent=False,
        issue_domain="test",
        issue_id="issue 2",
        learn_more_url=None,
        severity="warning",
        translation_key="abc_1234",
        translation_placeholders={"abc": "123"},
    )
    activated_issue_entry = issue_registry.async_get_issue("test", "issue 2")
    assert activated_issue_entry and activated_issue_entry.active
    assert issue_2_created == activated_issue_entry.created
    info = render_to_info(hass, "{{ issues()['test', 'issue 2'] }}")
    assert_result_info(info, activated_issue_entry.to_json())
    assert info.rate_limit is None


async def test_issue(hass: HomeAssistant, issue_registry: ir.IssueRegistry) -> None:
    """Test issue function."""
    # Test non existent issue
    info = render_to_info(hass, "{{ issue('non_existent', 'issue') }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    # Test existing issue
    ir.async_create_issue(
        hass,
        "test",
        "issue 1",
        breaks_in_ha_version="2023.7",
        is_fixable=True,
        is_persistent=True,
        learn_more_url="https://theuselessweb.com",
        severity="error",
        translation_key="abc_1234",
        translation_placeholders={"abc": "123"},
    )
    await hass.async_block_till_done()
    created_issue = issue_registry.async_get_issue("test", "issue 1")
    info = render_to_info(hass, "{{ issue('test', 'issue 1') }}")
    assert_result_info(info, created_issue.to_json())
    assert info.rate_limit is None


@pytest.mark.parametrize(
    ("disabled_by", "expected_issue_ids"),
    [
        pytest.param(None, ["entry_issue", "other_issue"], id="enabled"),
        pytest.param(ConfigEntryDisabler.USER, ["other_issue"], id="disabled"),
    ],
)
async def test_issues_of_config_entry(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    disabled_by: ConfigEntryDisabler | None,
    expected_issue_ids: list[str],
) -> None:
    """Test issues of disabled config entries are only hidden from issues()."""
    entry = MockConfigEntry(domain="test", disabled_by=disabled_by)
    entry.add_to_hass(hass)
    for issue_id, config_entry_id in (
        ("entry_issue", entry.entry_id),
        ("other_issue", None),
    ):
        ir.async_create_issue(
            hass,
            "test",
            issue_id,
            config_entry_id=config_entry_id,
            is_fixable=False,
            severity="error",
            translation_key="abc_1234",
        )

    info = render_to_info(hass, "{{ issues() }}")
    assert_result_info(
        info,
        {
            ("test", issue_id): issue_registry.async_get_issue(
                "test", issue_id
            ).to_json()
            for issue_id in expected_issue_ids
        },
    )

    # Direct lookup is not filtered
    info = render_to_info(hass, "{{ issue('test', 'entry_issue') }}")
    assert_result_info(
        info, issue_registry.async_get_issue("test", "entry_issue").to_json()
    )
