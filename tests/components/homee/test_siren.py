"""Test homee sirens."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.siren import (
    DOMAIN as SIREN_DOMAIN,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import async_update_attribute_value, build_mock_node, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def setup_siren(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_homee: MagicMock
) -> None:
    """Setups the integration siren tests."""
    mock_homee.nodes = [build_mock_node("siren.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)


@pytest.mark.parametrize(
    ("service", "target_value"),
    [
        (SERVICE_TURN_ON, 1),
        (SERVICE_TURN_OFF, 0),
        (SERVICE_TOGGLE, 1),
    ],
)
async def test_siren_services(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homee: MagicMock,
    service: str,
    target_value: int,
) -> None:
    """Test siren services."""
    await setup_siren(hass, mock_config_entry, mock_homee)

    await hass.services.async_call(
        SIREN_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "siren.test_siren"},
    )
    mock_homee.set_value.assert_called_once_with(1, 1, target_value)


async def test_siren_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homee: MagicMock,
) -> None:
    """Test siren state."""
    await setup_siren(hass, mock_config_entry, mock_homee)

    state = hass.states.get("siren.test_siren")
    assert state.state == "off"

    attribute = mock_homee.nodes[0].attributes[0]
    await async_update_attribute_value(hass, attribute, 1.0)
    state = hass.states.get("siren.test_siren")
    assert state.state == "on"


async def test_siren_snapshot(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homee: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test siren snapshot."""
    with patch("homeassistant.components.homee.PLATFORMS", [Platform.SIREN]):
        await setup_siren(hass, mock_config_entry, mock_homee)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
