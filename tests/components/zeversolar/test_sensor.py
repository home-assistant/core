"""Test the sensor classes."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion
from zeversolar.exceptions import ZeverSolarError

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    init_integration: MockConfigEntry,
) -> None:
    """Test sensors."""
    with patch(
        "homeassistant.components.zeversolar.PLATFORMS",
        [Platform.SENSOR],
    ):
        await snapshot_platform(
            hass, entity_registry, snapshot, init_integration.entry_id
        )


async def test_sensor_update_failed(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_zeversolar_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities become unavailable after a failed coordinator update."""
    assert hass.states.get("sensor.zeversolar_sensor_energy_today").state is not None

    mock_zeversolar_client.get_data.side_effect = ZeverSolarError
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.zeversolar_sensor_energy_today").state
        == STATE_UNAVAILABLE
    )
