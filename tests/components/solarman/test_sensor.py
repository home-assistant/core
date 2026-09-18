"""Tests for the Solarman sensor device."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.solarman.const import UPDATE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "device_fixture", ["P1-2W", "SP-2W-EU", "gl meter"], indirect=True
)
async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_solarman: AsyncMock,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test sensor platform."""
    with patch("homeassistant.components.solarman.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("device_fixture", ["SP-2W-EU"], indirect=True)
async def test_sensor_availability(
    hass: HomeAssistant,
    mock_solarman: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor availability."""
    with patch("homeassistant.components.solarman.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get("sensor.smart_plug_192_168_1_100_voltage"))
    assert state.state == "230"

    mock_solarman.fetch_data.side_effect = ConnectionError
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.smart_plug_192_168_1_100_voltage"))
    assert state.state == STATE_UNAVAILABLE
