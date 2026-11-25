"""Tests for the Sony Projector switch."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.sony_projector.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PLATFORM, STATE_ON
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import TEST_HOST

YAML_CONFIG = {
    SWITCH_DOMAIN: [
        {
            CONF_PLATFORM: DOMAIN,
            CONF_HOST: TEST_HOST,
            CONF_NAME: "Living Room Projector",
        }
    ]
}


@pytest.mark.usefixtures("mock_projector")
async def test_yaml_import_keeps_entity_id(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test an imported YAML platform keeps its entity ID and raises one issue."""
    assert await async_setup_component(hass, SWITCH_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert (state := hass.states.get("switch.living_room_projector"))
    assert state.state == STATE_ON
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


async def test_yaml_import_failure(
    hass: HomeAssistant,
    mock_projector: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a failed YAML import raises its own issue and creates no entry."""
    mock_projector.get_power.side_effect = ConnectionRefusedError

    assert await async_setup_component(hass, SWITCH_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert (
        issue := issue_registry.async_get_issue(
            DOMAIN, "deprecated_yaml_import_issue_cannot_connect"
        )
    )
    assert issue.severity is ir.IssueSeverity.ERROR
    assert not issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert not hass.config_entries.async_entries(DOMAIN)
