from unittest.mock import AsyncMock, patch
from datetime import timedelta

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from homeassistant.components.solarman.const import DEFAULT_SCAN_INTERVAL


from .conftest import setup_integration
from tests.common import MockConfigEntry, snapshot_platform, async_fire_time_changed

@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "device_fixture", ["P1-2W", "SP-2W-EU", "gl meter"], indirect=True
)
async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_solarman: AsyncMock,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry
) -> None:
    with patch("homeassistant.components.solarman.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "device_fixture", ["SP-2W-EU"], indirect=True
)
async def test_sensor_availability(
    hass: HomeAssistant, 
    mock_solarman: AsyncMock, 
    mock_config_entry: MockConfigEntry
) -> None:
    with patch("homeassistant.components.solarman.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)
    
    assert (state := hass.states.get("sensor.smart_plug_voltage"))
    assert state.state == "230"

    mock_solarman.fetch_data.side_effect = ConnectionError
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=DEFAULT_SCAN_INTERVAL))
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.smart_plug_voltage"))
    assert state.state == STATE_UNAVAILABLE
