"""Tests for the TRMNL switch platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_trmnl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all switch entities."""
    with patch("homeassistant.components.trmnl.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("service", "expected_value"),
    [
        (SERVICE_TURN_ON, True),
        (SERVICE_TURN_OFF, False),
    ],
)
async def test_set_switch(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    expected_value: bool,
) -> None:
    """Test turning the sleep mode switch on and off."""
    with patch("homeassistant.components.trmnl.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "switch",
        service,
        {ATTR_ENTITY_ID: "switch.test_trmnl_sleep_mode"},
        blocking=True,
    )

    mock_trmnl_client.update_device.assert_called_once_with(
        42793, sleep_mode_enabled=expected_value
    )
    assert mock_trmnl_client.get_devices.call_count == 2
