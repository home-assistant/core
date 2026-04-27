"""Tests for Comelit SimpleHome binary sensor platform."""

from unittest.mock import AsyncMock, patch

from aiocomelit.api import ComelitVedoAreaObject, ComelitVedoZoneObject
from aiocomelit.const import ALARM_AREA, ALARM_ZONE, AlarmAreaState, AlarmZoneState
from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.comelit.const import SCAN_INTERVAL
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_binary_sensor_entities_created(
    hass: HomeAssistant,
    mock_vedo: AsyncMock,
    mock_vedo_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test area and zone binary sensors are created."""
    with patch(
        "homeassistant.components.comelit.VEDO_PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, mock_vedo_config_entry)

    anomaly_entity_id = "binary_sensor.area0_anomaly"
    motion_entity_id = "binary_sensor.zone0_motion"
    faulty_entity_id = "binary_sensor.zone0_faulty"

    assert (state := hass.states.get(anomaly_entity_id))
    assert state.state == STATE_OFF
    assert (state := hass.states.get(motion_entity_id))
    assert state.state == STATE_OFF
    assert (state := hass.states.get(faulty_entity_id))
    assert state.state == STATE_OFF


async def test_binary_sensor_state_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_vedo: AsyncMock,
    mock_vedo_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test area anomaly and zone faulty binary sensor state updates."""
    with patch(
        "homeassistant.components.comelit.VEDO_PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, mock_vedo_config_entry)

    anomaly_entity_id = "binary_sensor.area0_anomaly"
    faulty_entity_id = "binary_sensor.zone0_faulty"

    mock_vedo.get_all_areas_and_zones.return_value = {
        ALARM_AREA: {
            0: ComelitVedoAreaObject(
                index=0,
                name="Area0",
                p1=True,
                p2=True,
                ready=False,
                armed=0,
                alarm=False,
                alarm_memory=False,
                sabotage=False,
                anomaly=True,
                in_time=False,
                out_time=False,
                human_status=AlarmAreaState.DISARMED,
            )
        },
        ALARM_ZONE: {
            0: ComelitVedoZoneObject(
                index=0,
                name="Zone0",
                status_api="0x000",
                status=0,
                human_status=AlarmZoneState.FAULTY,
            )
        },
    }

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(anomaly_entity_id))
    assert state.state == STATE_ON
    assert (state := hass.states.get(faulty_entity_id))
    assert state.state == STATE_ON
