"""Test the Helty Flow sensor platform."""

from dataclasses import replace
from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import make_data

from tests.common import MockConfigEntry, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_helty_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.helty.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_missing_readings_are_unknown(
    hass: HomeAssistant,
    mock_helty_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors report unknown when the unit omits a reading."""
    mock_helty_client.async_get_data.return_value = replace(
        make_data(),
        indoor_temperature=None,
        outdoor_temperature=None,
        indoor_humidity=None,
    )
    with patch("homeassistant.components.helty.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    for entity_id in (
        "sensor.vmc_soggiorno_indoor_temperature",
        "sensor.vmc_soggiorno_outdoor_temperature",
        "sensor.vmc_soggiorno_indoor_humidity",
    ):
        assert hass.states.get(entity_id).state == STATE_UNKNOWN
