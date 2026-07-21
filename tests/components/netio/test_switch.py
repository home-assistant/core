"""Tests for the Netio switch platform."""

from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from Netio.exceptions import CommunicationError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.netio.const import DOMAIN
from homeassistant.components.netio.coordinator import SCAN_INTERVAL
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_OUTPUT_1 = "switch.powercable_output_1"


@pytest.mark.usefixtures("mock_netio")
async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the switch entities and their states."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("service", "action_name"),
    [
        pytest.param(SERVICE_TURN_ON, "ON", id="turn_on"),
        pytest.param(SERVICE_TURN_OFF, "OFF", id="turn_off"),
    ],
)
async def test_switch_turn_on_off(
    hass: HomeAssistant,
    mock_netio: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    action_name: str,
) -> None:
    """Test turning a switch output on and off."""
    await setup_integration(hass, mock_config_entry)
    device = mock_netio.return_value

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_OUTPUT_1},
        blocking=True,
    )

    device.set_output.assert_called_once_with(
        1, getattr(mock_netio.ACTION, action_name)
    )


async def test_switch_action_error(
    hass: HomeAssistant,
    mock_netio: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an error while setting an output raises HomeAssistantError."""
    await setup_integration(hass, mock_config_entry)
    device = mock_netio.return_value
    device.set_output.side_effect = CommunicationError("failed")

    with pytest.raises(HomeAssistantError, match="Error setting output 1"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_OUTPUT_1},
            blocking=True,
        )


async def test_switch_unavailable(
    hass: HomeAssistant,
    mock_netio: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the switch becomes unavailable when the device cannot be reached."""
    await setup_integration(hass, mock_config_entry)
    device = mock_netio.return_value
    device.get_outputs.side_effect = CommunicationError("failed")

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_OUTPUT_1).state == STATE_UNAVAILABLE


async def test_legacy_yaml_creates_issue(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test the legacy YAML platform creates a deprecation repair issue."""
    with patch("homeassistant.components.netio.switch.Netio"):
        assert await async_setup_component(
            hass,
            SWITCH_DOMAIN,
            {
                SWITCH_DOMAIN: {
                    "platform": DOMAIN,
                    "host": "192.168.1.20",
                    "password": "legacy",
                    "outlets": {"1": "Lamp"},
                }
            },
        )
        await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, "deprecated_yaml")
