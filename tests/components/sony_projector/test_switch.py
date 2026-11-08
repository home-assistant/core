"""Tests for the Sony Projector switch."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sony_projector.const import DOMAIN
from homeassistant.components.sony_projector.coordinator import SCAN_INTERVAL
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_NAME,
    CONF_PLATFORM,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import TEST_HOST

ENTITY_ID = "switch.sony_projector"
YAML_CONFIG = {
    SWITCH_DOMAIN: [
        {
            CONF_PLATFORM: DOMAIN,
            CONF_HOST: TEST_HOST,
            CONF_NAME: "Living Room Projector",
        }
    ]
}


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_projector: MagicMock, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the integration."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry


async def test_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the switch entity."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.parametrize(
    ("service", "expected", "expected_state"),
    [
        pytest.param(SERVICE_TURN_ON, True, STATE_ON, id="on"),
        pytest.param(SERVICE_TURN_OFF, False, STATE_OFF, id="off"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_power_commands_keep_state_until_next_poll(
    hass: HomeAssistant,
    mock_projector: MagicMock,
    freezer: FrozenDateTimeFactory,
    service: str,
    expected: bool,
    expected_state: str,
) -> None:
    """Test the requested state holds while the projector reports its old state."""
    mock_projector.get_power.return_value = not expected

    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_projector.set_power.assert_called_once_with(expected)
    assert hass.states.get(ENTITY_ID).state == expected_state

    mock_projector.get_power.return_value = expected
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ENTITY_ID).state == expected_state


@pytest.mark.parametrize("error", [ConnectionRefusedError, Exception("Failed status")])
@pytest.mark.usefixtures("init_integration")
async def test_power_command_failure(
    hass: HomeAssistant, mock_projector: MagicMock, error: Exception
) -> None:
    """Test a failed power command raises an error."""
    mock_projector.set_power.side_effect = error

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
async def test_unavailable_and_recovery(
    hass: HomeAssistant,
    mock_projector: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the switch becomes unavailable when polling fails, then recovers."""
    mock_projector.get_power.side_effect = Exception("Timeout")
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    mock_projector.get_power.side_effect = None
    mock_projector.get_power.return_value = False
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ENTITY_ID).state == STATE_OFF


@pytest.mark.usefixtures("mock_projector")
async def test_yaml_import_keeps_entity_id(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test an imported YAML platform keeps its entity ID and raises one issue."""
    assert await async_setup_component(hass, SWITCH_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert hass.states.get("switch.living_room_projector").state == STATE_ON
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

    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect"
    )
    assert issue.severity is ir.IssueSeverity.ERROR
    assert not issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert not hass.config_entries.async_entries(DOMAIN)
