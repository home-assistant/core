"""Test the V2C select platform."""

from unittest.mock import AsyncMock, patch

from pytrydan.models.trydan import ChargeMode
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_select(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_v2c_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the select entities."""
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        await init_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_select_option(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test selecting an option."""
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        await init_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.evse_1_1_1_1_charge_mode",
            ATTR_OPTION: "mixed",
        },
        blocking=True,
    )

    mock_v2c_client.charge_mode.assert_awaited_once_with(ChargeMode.MIXED)


async def test_select_disabled_when_missing(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_v2c_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test missing charge mode entity is disabled."""
    mock_v2c_client.get_data.return_value.charge_mode = None

    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        await init_integration(hass, mock_config_entry)

    entity_id = "select.evse_1_1_1_1_charge_mode"
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(entity_id) is None
