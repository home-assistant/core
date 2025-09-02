"""Test Nederlandse Spoorwegen repair notifications."""

from unittest.mock import patch

from homeassistant.components.nederlandse_spoorwegen import async_setup
from homeassistant.components.nederlandse_spoorwegen.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir


async def test_platform_migration_creates_repair_issue(hass: HomeAssistant) -> None:
    """Test that platform-based configuration creates a repair issue."""
    config = {
        "sensor": [
            {
                "platform": DOMAIN,
                CONF_API_KEY: "test_api_key",
                "routes": [{"name": "Test Route", "from": "Asd", "to": "Rtd"}],
            }
        ]
    }

    with patch.object(hass.config_entries.flow, "async_init") as mock_flow:
        result = await async_setup(hass, config)

    assert result is True
    mock_flow.assert_called_once()

    # Check that repair issue was created
    issue_registry = ir.async_get(hass)
    issues = issue_registry.issues

    assert (DOMAIN, "platform_yaml_migration") in issues
    issue = issues[(DOMAIN, "platform_yaml_migration")]
    assert issue.translation_key == "platform_yaml_migration"
    assert issue.severity == ir.IssueSeverity.WARNING


async def test_integration_migration_creates_repair_issue(hass: HomeAssistant) -> None:
    """Test that integration-level configuration creates a repair issue."""
    config = {
        DOMAIN: {
            CONF_API_KEY: "test_api_key",
            "routes": [{"name": "Test Route", "from": "Asd", "to": "Rtd"}],
        }
    }

    with patch.object(hass.config_entries.flow, "async_init") as mock_flow:
        result = await async_setup(hass, config)

    assert result is True
    mock_flow.assert_called_once()

    # Check that repair issue was created
    issue_registry = ir.async_get(hass)
    issues = issue_registry.issues

    assert (DOMAIN, "integration_yaml_migration") in issues
    issue = issues[(DOMAIN, "integration_yaml_migration")]
    assert issue.translation_key == "integration_yaml_migration"
    assert issue.severity == ir.IssueSeverity.WARNING


async def test_no_config_no_repair_issue(hass: HomeAssistant) -> None:
    """Test that no configuration doesn't create repair issues."""
    config = {}

    with patch.object(hass.config_entries.flow, "async_init") as mock_flow:
        result = await async_setup(hass, config)

    assert result is True
    mock_flow.assert_not_called()

    # Check that no repair issues were created
    issue_registry = ir.async_get(hass)
    issues = issue_registry.issues

    assert (DOMAIN, "platform_yaml_migration") not in issues
    assert (DOMAIN, "integration_yaml_migration") not in issues


async def test_multiple_platform_configs_only_creates_one_issue(
    hass: HomeAssistant,
) -> None:
    """Test that multiple platform configs only create one repair issue."""
    config = {
        "sensor": [
            {
                "platform": DOMAIN,
                CONF_API_KEY: "test_api_key1",
                "routes": [{"name": "Route 1", "from": "Asd", "to": "Rtd"}],
            },
            {
                "platform": "other_platform",
                "some_other_config": "value",
            },
            {
                "platform": DOMAIN,
                CONF_API_KEY: "test_api_key2",
                "routes": [{"name": "Route 2", "from": "Rtd", "to": "Asd"}],
            },
        ]
    }

    with patch.object(hass.config_entries.flow, "async_init") as mock_flow:
        result = await async_setup(hass, config)

    assert result is True
    # Should only trigger one import flow (stops after first match)
    mock_flow.assert_called_once()

    # Check that only one repair issue was created
    issue_registry = ir.async_get(hass)
    issues = issue_registry.issues

    platform_issues = [
        issue_id
        for (domain, issue_id) in issues
        if domain == DOMAIN and issue_id == "platform_yaml_migration"
    ]
    assert len(platform_issues) == 1


async def test_cleanup_migration_issues_when_no_yaml_config(
    hass: HomeAssistant,
) -> None:
    """Test that migration issues are cleaned up when no YAML config exists."""
    issue_registry = ir.async_get(hass)

    # Manually create some migration issues
    ir.async_create_issue(
        hass,
        DOMAIN,
        "integration_yaml_migration",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="integration_yaml_migration",
    )
    ir.async_create_issue(
        hass,
        DOMAIN,
        "platform_yaml_migration",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="platform_yaml_migration",
    )

    # Verify issues exist
    assert (DOMAIN, "integration_yaml_migration") in issue_registry.issues
    assert (DOMAIN, "platform_yaml_migration") in issue_registry.issues

    # Call async_setup with no YAML configuration
    config = {}
    await async_setup(hass, config)

    # Verify issues are cleaned up
    assert (DOMAIN, "integration_yaml_migration") not in issue_registry.issues
    assert (DOMAIN, "platform_yaml_migration") not in issue_registry.issues
