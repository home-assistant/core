"""Test switch platform."""

from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_switch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test switch platform."""
    with patch(
        "homeassistant.components.nintendo_parental_controls._PLATFORMS",
        [Platform.SWITCH],
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

async def test_suspend_software(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
    mock_nintendo_device: AsyncMock,
) -> None:
    """Test switch platform."""
    with patch(
        "homeassistant.components.nintendo_parental_controls._PLATFORMS",
        [Platform.SWITCH],
    ):
        await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        target={ATTR_ENTITY_ID: "switch.home_assistant_test_suspend_software"},
        blocking=True,
    )
    assert len(mock_nintendo_device.set_restriction_mode.mock_calls) == 1
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        target={ATTR_ENTITY_ID: "switch.home_assistant_test_suspend_software"},
        blocking=True,
    )
    assert len(mock_nintendo_device.set_restriction_mode.mock_calls) == 2
