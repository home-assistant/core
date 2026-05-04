"""Test the V2C number platform."""

from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_number(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_v2c_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the number entities."""
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.NUMBER]):
        await init_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_number_set_value(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting number values."""
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.NUMBER]):
        await init_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.evse_1_1_1_1_installation_voltage",
            ATTR_VALUE: 240,
        },
        blocking=True,
    )

    mock_v2c_client.voltage_installation.assert_called_once_with(240)
