"""Tests for Comelit SimpleHome coordinator."""

from unittest.mock import AsyncMock

from aiocomelit.api import (
    AlarmDataObject,
    ComelitSerialBridgeObject,
    ComelitVedoAreaObject,
    ComelitVedoZoneObject,
)
from aiocomelit.const import (
    CLIMATE,
    COVER,
    IRRIGATION,
    LIGHT,
    OTHER,
    SCENARIO,
    WATT,
    AlarmAreaState,
    AlarmZoneState,
)
from aiocomelit.exceptions import CannotAuthenticate, CannotConnect, CannotRetrieveData
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.comelit.const import SCAN_INTERVAL
from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import setup_integration
from .const import LIGHT0, ZONE0

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize(
    "side_effect",
    [
        CannotConnect,
        CannotRetrieveData,
        CannotAuthenticate,
    ],
)
async def test_coordinator_data_update_fails(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
    side_effect: Exception,
) -> None:
    """Test coordinator data update exceptions."""

    entity_id = "light.light0"

    await setup_integration(hass, mock_serial_bridge_config_entry)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF

    mock_serial_bridge.login.side_effect = side_effect

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNAVAILABLE


async def test_coordinator_stale_device_serial_bridge(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator data update removes stale Serial Brdige devices."""

    entity_id_0 = "light.light0"
    entity_id_1 = "light.light1"

    mock_serial_bridge.get_all_devices.return_value = {
        CLIMATE: {},
        COVER: {},
        LIGHT: {
            0: LIGHT0,
            1: ComelitSerialBridgeObject(
                index=1,
                name="Light1",
                status=0,
                human_status="off",
                type="light",
                val=0,
                protected=0,
                zone="Bathroom",
                power=0.0,
                power_unit=WATT,
            ),
        },
        OTHER: {},
        IRRIGATION: {},
        SCENARIO: {},
    }

    await setup_integration(hass, mock_serial_bridge_config_entry)

    assert (state := hass.states.get(entity_id_0))
    assert state.state == STATE_OFF
    assert (state := hass.states.get(entity_id_1))
    assert state.state == STATE_OFF

    mock_serial_bridge.get_all_devices.return_value = {
        CLIMATE: {},
        COVER: {},
        LIGHT: {0: LIGHT0},
        OTHER: {},
        IRRIGATION: {},
        SCENARIO: {},
    }

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id_0))
    assert state.state == STATE_OFF

    # Light1 is removed
    assert not hass.states.get(entity_id_1)


async def test_coordinator_stale_device_vedo(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_vedo: AsyncMock,
    mock_vedo_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator data update removes stale VEDO devices."""

    entity_id_0 = "sensor.zone0"
    entity_id_1 = "sensor.zone1"

    mock_vedo.get_all_areas_and_zones.return_value = AlarmDataObject(
        alarm_areas={
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
                anomaly=False,
                in_time=False,
                out_time=False,
                human_status=AlarmAreaState.DISARMED,
            )
        },
        alarm_zones={
            0: ZONE0,
            1: ComelitVedoZoneObject(
                index=1,
                name="Zone1",
                status_api="0x000",
                status=0,
                human_status=AlarmZoneState.REST,
            ),
        },
    )
    await setup_integration(hass, mock_vedo_config_entry)

    assert (state := hass.states.get(entity_id_0))
    assert state.state == AlarmZoneState.REST.value
    assert (state := hass.states.get(entity_id_1))
    assert state.state == AlarmZoneState.REST.value

    mock_vedo.get_all_areas_and_zones.return_value = AlarmDataObject(
        alarm_areas={
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
                anomaly=False,
                in_time=False,
                out_time=False,
                human_status=AlarmAreaState.DISARMED,
            )
        },
        alarm_zones={
            0: ZONE0,
        },
    )

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id_0))
    assert state.state == AlarmZoneState.REST.value

    # Zone1 is removed
    assert not hass.states.get(entity_id_1)
