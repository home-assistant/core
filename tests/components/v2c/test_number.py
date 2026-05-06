"""Test the V2C number platform."""

from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.v2c.const import DOMAIN
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


async def test_remove_old_installation_voltage_sensor_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_v2c_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test removing the old installation voltage sensor entity."""
    mock_config_entry.add_to_hass(hass)
    unique_id = f"{mock_config_entry.entry_id}_voltage_installation"
    old_entity_id = "sensor.evse_1_1_1_1_installation_voltage"
    new_entity_id = "number.evse_1_1_1_1_installation_voltage"
    entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        unique_id,
        suggested_object_id="evse_1_1_1_1_installation_voltage",
        config_entry=mock_config_entry,
    )

    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.NUMBER]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    new_entry = entity_registry.async_get(new_entity_id)
    assert entity_registry.async_get(old_entity_id) is None
    assert new_entry is not None
    assert new_entry.unique_id == unique_id
    assert (
        entity_registry.async_get_entity_id(Platform.NUMBER, DOMAIN, unique_id)
        == new_entity_id
    )
    assert hass.states.get(new_entity_id) is not None
