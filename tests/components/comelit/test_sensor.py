"""Tests for Comelit SimpleHome sensor platform."""

from unittest.mock import AsyncMock, patch

from aiocomelit.api import AlarmDataObject, ComelitVedoAreaObject, ComelitVedoZoneObject
from aiocomelit.const import AlarmAreaState, AlarmZoneState
from freezegun.api import FrozenDateTimeFactory
from syrupy import SnapshotAssertion

from homeassistant.components.comelit.const import SCAN_INTERVAL
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "sensor.zone0"


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_vedo: AsyncMock,
    mock_vedo_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.comelit.VEDO_PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_vedo_config_entry)

    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_vedo_config_entry.entry_id,
    )


async def test_sensor_state_unknown(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_vedo: AsyncMock,
    mock_vedo_config_entry: MockConfigEntry,
) -> None:
    """Test sensor unknown state."""

    await setup_integration(hass, mock_vedo_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == AlarmZoneState.REST.value

    vedo_query = AlarmDataObject(
        alarm_areas={
            0: ComelitVedoAreaObject(
                index=0,
                name="Area0",
                p1=True,
                p2=True,
                ready=False,
                armed=True,
                alarm=False,
                alarm_memory=False,
                sabotage=False,
                anomaly=False,
                in_time=False,
                out_time=False,
                human_status=AlarmAreaState.UNKNOWN,
            )
        },
        alarm_zones={
            0: ComelitVedoZoneObject(
                index=0,
                name="Zone0",
                status_api="0x000",
                status=0,
                human_status=AlarmZoneState.UNKNOWN,
            )
        },
    )

    mock_vedo.get_all_areas_and_zones.return_value = vedo_query

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNKNOWN
