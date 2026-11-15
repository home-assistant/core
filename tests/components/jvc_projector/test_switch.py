"""Tests for JVC Projector switch platform."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from jvcprojector import command as cmd
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchService
from homeassistant.const import CommonServiceArgument, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

ESHIFT_ENTITY_ID = "switch.jvc_projector_e_shift"
LOW_LATENCY_ENTITY_ID = "switch.jvc_projector_low_latency_mode"


@pytest.fixture(autouse=True)
def platform() -> Generator[AsyncMock]:
    """Fixture for platform."""
    with patch("homeassistant.components.jvc_projector.PLATFORMS", [Platform.SWITCH]):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entities(
    hass: HomeAssistant,
    mock_device: MagicMock,
    mock_integration: MockConfigEntry,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_device: MagicMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Test switch entities."""

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SwitchService.TURN_OFF,
        {CommonServiceArgument.ENTITY_ID: ESHIFT_ENTITY_ID},
        blocking=True,
    )

    mock_device.set.assert_any_call(cmd.EShift, "off")

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SwitchService.TURN_ON,
        {CommonServiceArgument.ENTITY_ID: ESHIFT_ENTITY_ID},
        blocking=True,
    )

    mock_device.set.assert_any_call(cmd.EShift, "on")
