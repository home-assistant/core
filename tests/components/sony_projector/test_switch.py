"""Tests for the Sony Projector switch."""

import dataclasses
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.sony_projector.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    CONF_ENTITY_NAMESPACE,
    CONF_HOST,
    CONF_NAME,
    CONF_PLATFORM,
    STATE_ON,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import TEST_HOST

UNREACHABLE_HOST = "192.0.2.20"
ISSUE_PLACEHOLDERS = {"domain": DOMAIN, "integration_title": "Sony Projector"}
YAML_CONFIG = {
    SWITCH_DOMAIN: [
        {
            CONF_PLATFORM: DOMAIN,
            CONF_HOST: TEST_HOST,
            CONF_NAME: "Living Room Projector",
        }
    ]
}


@pytest.mark.parametrize(
    ("extra_config", "expected_entity_id"),
    [
        pytest.param({}, "switch.living_room_projector", id="name"),
        pytest.param(
            {CONF_ENTITY_NAMESPACE: "upstairs"},
            "switch.upstairs_living_room_projector",
            id="namespace",
        ),
    ],
)
@pytest.mark.usefixtures("mock_projector")
async def test_yaml_import_keeps_entity_id(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    extra_config: dict[str, str],
    expected_entity_id: str,
) -> None:
    """Test an imported YAML platform keeps its entity ID and raises one issue."""
    config = {SWITCH_DOMAIN: [YAML_CONFIG[SWITCH_DOMAIN][0] | extra_config]}
    assert await async_setup_component(hass, SWITCH_DOMAIN, config)
    await hass.async_block_till_done()

    assert hass.states.get(expected_entity_id).state == STATE_ON
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures("mock_projector")
async def test_yaml_import_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test YAML left in place after the import still raises the issue."""
    mock_config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, SWITCH_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_yaml_import_partial_failure(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a successful import doesn't raise the warning after another failed."""

    def create_projector(host: str) -> MagicMock:
        """Return a projector that only answers on the reachable host."""
        projector = MagicMock()
        projector.get_power.side_effect = (
            ConnectionRefusedError if host == UNREACHABLE_HOST else None
        )
        return projector

    config = {
        SWITCH_DOMAIN: [
            {CONF_PLATFORM: DOMAIN, CONF_HOST: host, CONF_NAME: host}
            for host in (TEST_HOST, UNREACHABLE_HOST)
        ]
    }
    with patch("pysdcp.Projector", side_effect=create_projector):
        assert await async_setup_component(hass, SWITCH_DOMAIN, config)
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect"
    )
    assert not issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


async def test_yaml_import_failure_removes_warning(
    hass: HomeAssistant, mock_projector: MagicMock, issue_registry: ir.IssueRegistry
) -> None:
    """Test a failed import removes the warning raised by an earlier success."""
    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders=ISSUE_PLACEHOLDERS,
    )
    mock_projector.get_power.side_effect = ConnectionRefusedError

    assert await async_setup_component(hass, SWITCH_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert not issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.usefixtures("mock_projector")
async def test_yaml_import_ignores_failure_from_previous_start(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test an import failure restored from storage doesn't hide the warning."""
    issue_id = "deprecated_yaml_import_issue_cannot_connect"
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key=issue_id,
        translation_placeholders=ISSUE_PLACEHOLDERS,
    )
    issue_registry.issues[(DOMAIN, issue_id)] = dataclasses.replace(
        issue_registry.async_get_issue(DOMAIN, issue_id), active=False
    )

    assert await async_setup_component(hass, SWITCH_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


async def test_yaml_import_failure(
    hass: HomeAssistant,
    mock_projector: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a failed YAML import raises its own issue and creates no entry."""
    mock_projector.get_power.side_effect = ConnectionRefusedError

    assert await async_setup_component(hass, SWITCH_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect"
    )
    assert issue.severity is ir.IssueSeverity.ERROR
    assert not issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert not hass.config_entries.async_entries(DOMAIN)
