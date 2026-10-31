"""Tests for the Flexit Nordic (BACnet) sensor entities."""

from unittest.mock import AsyncMock

from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.flexit_bacnet.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_with_selected_platforms


async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_flexit_bacnet: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor states are correctly collected from library."""

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_extract_air_humidity_not_supported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_flexit_bacnet: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test extract air humidity sensor is not created on units without the sensor."""
    mock_flexit_bacnet.extract_air_humidity = 0.0

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    assert hass.states.get("sensor.device_name_extract_air_temperature")
    assert not entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, "0000-0001-extract_air_humidity"
    )
