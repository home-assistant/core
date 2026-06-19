"""Tests for the Cync integration switch platform."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

PLUG_DEVICE_ID = 1201
PLUG_ENTITY_ID = "switch.bedroom_bedroom_plug"


@pytest.fixture(autouse=True)
def switch_platform_only():
    """Limit platform setup to switch only."""
    with patch("homeassistant.components.cync._PLATFORMS", [Platform.SWITCH]):
        yield


async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that switch attributes are properly set on setup."""

    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("service", "expected_is_on"),
    [
        ("turn_on", True),
        ("turn_off", False),
    ],
    ids=["turn_on", "turn_off"],
)
async def test_switch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    service: str,
    expected_is_on: bool,
) -> None:
    """Test that turning on/off the plug calls set_power_state with the correct value."""

    await setup_integration(hass, mock_config_entry)

    test_device = mock_config_entry.runtime_data.data.get(PLUG_DEVICE_ID)
    mock_client = MagicMock()
    mock_client.set_power_state = AsyncMock(name="set_power_state")
    test_device._command_client = mock_client

    await hass.services.async_call(
        "switch",
        service,
        {"entity_id": PLUG_ENTITY_ID},
        blocking=True,
    )

    mock_client.set_power_state.assert_called_once_with(test_device, expected_is_on)
