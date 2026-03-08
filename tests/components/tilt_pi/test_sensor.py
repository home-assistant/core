"""Test the Tilt Hydrometer sensors."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion
from tiltpi import TiltColor, TiltPiConnectionError

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_all_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tiltpi_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Tilt Pi sensors.

    When making changes to this test, ensure that the snapshot reflects the
    new data by generating it via:

        $ pytest tests/components/tilt_pi/test_sensor.py -v --snapshot-update
    """
    with patch("homeassistant.components.tilt_pi.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_availability(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tiltpi_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that entities become unavailable when the coordinator fails."""
    with patch("homeassistant.components.tilt_pi.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    # Simulate a coordinator update failure
    mock_tiltpi_client.get_hydrometers.side_effect = TiltPiConnectionError()
    freezer.tick(60)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Check that entities are unavailable
    for color in (TiltColor.BLACK, TiltColor.YELLOW):
        temperature_entity_id = f"sensor.tilt_{color}_temperature"
        gravity_entity_id = f"sensor.tilt_{color}_gravity"

        temperature_state = hass.states.get(temperature_entity_id)
        assert temperature_state is not None
        assert temperature_state.state == STATE_UNAVAILABLE

        gravity_state = hass.states.get(gravity_entity_id)
        assert gravity_state is not None
        assert gravity_state.state == STATE_UNAVAILABLE

    # Simulate a coordinator update success
    mock_tiltpi_client.get_hydrometers.side_effect = None
    freezer.tick(60)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Check that entities are now available
    for color in (TiltColor.BLACK, TiltColor.YELLOW):
        temperature_entity_id = f"sensor.tilt_{color}_temperature"
        gravity_entity_id = f"sensor.tilt_{color}_gravity"

        temperature_state = hass.states.get(temperature_entity_id)
        assert temperature_state is not None
        assert temperature_state.state != STATE_UNAVAILABLE

        gravity_state = hass.states.get(gravity_entity_id)
        assert gravity_state is not None
        assert gravity_state.state != STATE_UNAVAILABLE
