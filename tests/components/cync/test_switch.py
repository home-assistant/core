"""Tests for the Cync integration switch platform."""

from unittest.mock import AsyncMock, patch

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
    ("service", "device_method", "other_method"),
    [
        ("turn_on", "turn_on", "turn_off"),
        ("turn_off", "turn_off", "turn_on"),
    ],
    ids=["turn_on", "turn_off"],
)
async def test_switch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    service: str,
    device_method: str,
    other_method: str,
) -> None:
    """Test that turning on/off the plug calls the device on/off methods."""

    await setup_integration(hass, mock_config_entry)

    test_device = mock_config_entry.runtime_data.data.get(PLUG_DEVICE_ID)
    test_device.turn_on = AsyncMock(name="turn_on")
    test_device.turn_off = AsyncMock(name="turn_off")

    await hass.services.async_call(
        "switch",
        service,
        {"entity_id": PLUG_ENTITY_ID},
        blocking=True,
    )

    getattr(test_device, device_method).assert_called_once()
    getattr(test_device, other_method).assert_not_called()
