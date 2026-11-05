"""Tests for repairs issue_handler.py."""

from typing import Any

import pytest
from pytest_homeassistant.common import (
    AsyncMock,
    Mock,
    MockModule,
    async_setup_component,
    mock_integration,
    mock_platform,
)

from homeassistant.components.repairs import (
    DOMAIN,
    RepairsFlow,
    RepairsFlowResult,
    repairs_flow_manager,
)
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant
import homeassistant.helpers.issue_registry as ir


@pytest.fixture(autouse=True)
async def mock_repairs_integration(hass: HomeAssistant) -> None:
    """Mock a repairs integration."""
    hass.config.components.add("fake_integration")

    async def async_create_fix_flow(
        hass: HomeAssistant,
        issue_id: str,
        data: dict[str, str | int | float | None] | None,
    ) -> RepairsFlow:
        return MockFixFlowContext()

    mock_platform(
        hass,
        "fake_integration.repairs",
        Mock(async_create_fix_flow=AsyncMock(wraps=async_create_fix_flow)),
    )


class MockFixFlowContext(RepairsFlow):
    """Mock for context tests."""

    async def async_step_init(self, user_input: dict | None) -> RepairsFlowResult:
        """Initial step of a repairs flow."""
        # check that legacy behavior intact
        assert user_input and user_input.get("issue_id") == self.issue_id
        return self.async_show_form(step_id="init")


@pytest.mark.parametrize(
    ("ignore_translations_for_mock_domains"),
    [
        ["fake_integration"],
    ],
)
async def test_flow_fix_via_data_deprecation(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that a repairs flow's issue_id can be set via data but logs a deprecation."""

    assert await async_setup_component(hass, DOMAIN, {})

    ir.async_create_issue(
        hass,
        issue_id="context_issue",
        domain="fake_integration",
        is_fixable=True,
        severity="error",
        translation_key="fake_key",
    )

    repairs = repairs_flow_manager(hass)

    result = await repairs.async_init(
        "fake_integration", data={"issue_id": "context_issue"}
    )
    assert any(
        "initiates a repair flow by passing `issue_id` via `data` rather than `context`"
        in msg
        for msg in caplog.messages
    )
    assert result["type"] == "form"
    result = repairs.async_get(result["flow_id"])
    assert result["context"] == {"issue_id": "context_issue"}


@pytest.mark.parametrize(
    ("ignore_translations_for_mock_domains"),
    [
        ["fake_integration"],
    ],
)
async def test_flow_fix_missing_context(hass: HomeAssistant) -> None:
    """Test that KeyError is thrown when context and data is missing."""

    assert await async_setup_component(hass, DOMAIN, {})

    repairs = repairs_flow_manager(hass)

    with pytest.raises(KeyError) as exc:
        await repairs.async_init("fake_integration")

    assert "issue_id was not set in context" in str(exc.value)


def _stored_issue(
    domain: str,
    issue_id: str,
    translation_key: str,
    *,
    dismissed_version: str | None = None,
    is_persistent: bool = True,
    issue_domain: str | None = None,
) -> dict[str, Any]:
    """Return an issue as it is stored."""
    return {
        "breaks_in_ha_version": None,
        "config_entry_id": None,
        "config_subentry_id": None,
        "created": "2022-07-19T07:53:05+00:00",
        "data": None,
        "dismissed_version": dismissed_version,
        "domain": domain,
        "is_fixable": False,
        "is_persistent": is_persistent,
        "issue_domain": issue_domain,
        "issue_id": issue_id,
        "learn_more_url": None,
        "severity": "warning",
        "translation_key": translation_key,
        "translation_placeholders": None,
    }


async def test_delete_stale_issues_at_started(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test persistent issues of core integrations without translation are deleted."""
    mock_integration(hass, MockModule("test_custom"), built_in=False)
    mock_integration(
        hass, MockModule("test_no_translations"), built_in=True, top_level_files=set()
    )
    hass_storage[ir.STORAGE_KEY] = {
        "version": ir.STORAGE_VERSION_MAJOR,
        "minor_version": ir.STORAGE_VERSION_MINOR,
        "data": {
            "issues": [
                _stored_issue("automation", "current", "service_not_found"),
                _stored_issue("automation", "stale", "removed"),
                _stored_issue(
                    "automation", "stale_ignored", "removed", dismissed_version="2022.7"
                ),
                # Translations are looked up by domain, like the frontend does
                _stored_issue(
                    "automation",
                    "other_issue_domain",
                    "service_not_found",
                    issue_domain="test_custom",
                ),
                # Non persistent issues load without their translation key
                _stored_issue(
                    "automation", "not_persistent", "removed", is_persistent=False
                ),
                _stored_issue("test_custom", "custom", "removed"),
                _stored_issue("test_no_translations", "no_translations", "removed"),
                _stored_issue("unknown_domain", "unknown", "removed"),
            ]
        },
    }
    await ir.async_load(hass)
    issue_registry = ir.async_get(hass)
    all_issues = set(issue_registry.issues)
    assert len(all_issues) == 8

    hass.set_state(CoreState.not_running)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert set(issue_registry.issues) == all_issues

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    assert set(issue_registry.issues) == all_issues - {
        ("automation", "stale"),
        ("automation", "stale_ignored"),
        ("test_no_translations", "no_translations"),
    }


async def test_delete_stale_issues_when_started(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test stale issues are deleted when repairs is set up after start."""
    hass_storage[ir.STORAGE_KEY] = {
        "version": ir.STORAGE_VERSION_MAJOR,
        "minor_version": ir.STORAGE_VERSION_MINOR,
        "data": {
            "issues": [
                _stored_issue("automation", "current", "service_not_found"),
                _stored_issue("automation", "stale", "removed"),
            ]
        },
    }
    await ir.async_load(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert set(ir.async_get(hass).issues) == {("automation", "current")}
