"""Test the Helty Flow Cloud sensor platform."""

from unittest.mock import AsyncMock, patch

from pyheltycloud import HeltyState, VmcMode
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_helty_cloud")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.helty_cloud.PLATFORMS",
        [Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_missing_readings(
    hass: HomeAssistant,
    mock_helty_cloud: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test readings the panel did not send are unknown, not zero."""
    mock_helty_cloud.get_last_telemetry.side_effect = lambda serial: HeltyState(
        mode=VmcMode.SPEED_1
    )
    await setup_integration(hass, mock_config_entry)

    for entity_id in (
        "sensor.vmc_soggiorno_indoor_temperature",
        "sensor.vmc_soggiorno_outdoor_temperature",
        "sensor.vmc_soggiorno_indoor_humidity",
        "sensor.vmc_soggiorno_air_treated_by_filter",
        "sensor.vmc_soggiorno_total_air_treated",
    ):
        assert hass.states.get(entity_id).state == STATE_UNKNOWN
