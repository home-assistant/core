"""Tests for Midea sensor.py."""

from collections.abc import Callable
from unittest.mock import patch

from midealocal.const import DeviceType
from midealocal.devices.ac import DeviceAttributes as ACAttributes
from midealocal.devices.c3 import DeviceAttributes as C3Attributes
from midealocal.devices.db import DeviceAttributes as DBAttributes
from midealocal.devices.e8 import DeviceAttributes as E8Attributes
from midealocal.devices.ea import DeviceAttributes as EAAttributes
from midealocal.devices.ec import DeviceAttributes as ECAttributes
from midealocal.devices.ed import DeviceAttributes as EDAttributes
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import DummyDevice, SetDeviceAttribute, entity_entries
from .const import TEST_DEVICE_ID

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize(
    "device",
    [
        pytest.param(
            DummyDevice(
                DeviceType.AC,
                attributes={
                    ACAttributes.power: True,
                    ACAttributes.mode: 1,
                    ACAttributes.target_temperature: 22.0,
                    ACAttributes.indoor_temperature: 21.0,
                    ACAttributes.comfort_mode: False,
                    ACAttributes.eco_mode: False,
                    ACAttributes.boost_mode: False,
                    ACAttributes.sleep_mode: False,
                    ACAttributes.frost_protect: False,
                    ACAttributes.fan_speed: 103,
                    ACAttributes.swing_vertical: True,
                    ACAttributes.swing_horizontal: True,
                    ACAttributes.indoor_humidity: 50,
                },
            ),
            id="ac",
        ),
        pytest.param(
            DummyDevice(
                DeviceType.C3,
                attributes={
                    C3Attributes.zone_temp_type: [True, False],
                    C3Attributes.temperature_min: [16, 17],
                    C3Attributes.temperature_max: [30, 29],
                    C3Attributes.mode: 1,
                    C3Attributes.zone1_power: True,
                    C3Attributes.zone2_power: False,
                    C3Attributes.target_temperature: [22, 23],
                    C3Attributes.temp_tw_out: 21.5,
                },
            ),
            id="c3",
        ),
        pytest.param(
            DummyDevice(
                DeviceType.E8,
                attributes={
                    E8Attributes.status: 1,
                    E8Attributes.time_remaining: 3600,
                    E8Attributes.keep_warm_remaining: 1800,
                    E8Attributes.working_time: 7200,
                    E8Attributes.target_temperature: 22.0,
                    E8Attributes.current_temperature: 21.0,
                    E8Attributes.finished: False,
                    E8Attributes.water_shortage: False,
                },
            ),
            id="e8",
        ),
        pytest.param(
            DummyDevice(
                DeviceType.DB,
                attributes={
                    DBAttributes.power: True,
                    DBAttributes.mode: "normal",
                    DBAttributes.temperature: 22.0,
                    DBAttributes.wash_time: 65,
                    DBAttributes.dehydration_time: 30,
                    DBAttributes.program: "cotton",
                },
            ),
            id="db",
        ),
        pytest.param(
            DummyDevice(
                DeviceType.DB,
                attributes={
                    DBAttributes.power: False,
                    DBAttributes.mode: "unknown",
                    DBAttributes.temperature: 22.0,
                    DBAttributes.wash_time: 65,
                    DBAttributes.dehydration_time: 30,
                    DBAttributes.program: "unknown",
                },
            ),
            id="db_unknown_attributes",
        ),
        pytest.param(
            DummyDevice(
                DeviceType.EA,
                attributes={
                    EAAttributes.bottom_temperature: 180,
                    EAAttributes.cooking: 1,
                    EAAttributes.keep_warm: True,
                    EAAttributes.mode: "heat_rice",
                    EAAttributes.progress: 50,
                    EAAttributes.keep_warm_time: 30,
                    EAAttributes.time_remaining: 5,
                    EAAttributes.top_temperature: 200,
                },
            ),
            id="ea",
        ),
        pytest.param(
            DummyDevice(
                DeviceType.EC,
                attributes={
                    ECAttributes.cooking: 1,
                    ECAttributes.mode: "diy",
                    ECAttributes.progress: 50,
                    ECAttributes.keep_warm_time: 30,
                    ECAttributes.time_remaining: 5,
                    ECAttributes.top_temperature: 200,
                    ECAttributes.with_pressure: True,
                },
            ),
            id="ec",
        ),
        pytest.param(
            DummyDevice(
                DeviceType.ED,
                attributes={
                    EDAttributes.keep_warm: True,
                    EDAttributes.boil_temperature: 100,
                    EDAttributes.boiling: True,
                    EDAttributes.keep_warm_time: 30,
                    EDAttributes.child_lock: True,
                    EDAttributes.cl_sterilization: True,
                    EDAttributes.cooling: True,
                    EDAttributes.current_temperature: 150,
                    EDAttributes.dispensing: True,
                    EDAttributes.error: 3,
                    EDAttributes.filter1: 30,
                    EDAttributes.filter2: 20,
                    EDAttributes.filter3: 100,
                    EDAttributes.flushing_days: 50,
                    EDAttributes.heating: True,
                    EDAttributes.hot_water_dispensing: True,
                    EDAttributes.in_tds: 200,
                    EDAttributes.keep_warm_remaining: 20,
                    EDAttributes.lack_water: True,
                    EDAttributes.leak_water: True,
                    EDAttributes.out_tds: 100,
                    EDAttributes.power: True,
                    EDAttributes.water_consumption: 500,
                    EDAttributes.water_consumption_big: 6000,
                    EDAttributes.water_consumption_average: 30,
                },
            ),
            id="ed",
        ),
    ],
)
async def test_all_entities(
    hass: HomeAssistant,
    device: DummyDevice,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor entities are created."""
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry, device)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_sensor_state_update(
    hass: HomeAssistant,
    set_device_attribute: SetDeviceAttribute,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test sensor state follows push updates from the device."""
    device = DummyDevice(
        DeviceType.AC,
        attributes={
            ACAttributes.power: True,
            ACAttributes.mode: 1,
            ACAttributes.target_temperature: 22.0,
            ACAttributes.indoor_temperature: 21.0,
            ACAttributes.indoor_humidity: 0,
            ACAttributes.full_dust: False,
            ACAttributes.outdoor_temperature: "unknown",
        },
    )
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry, device)

    assert len(entity_entries(hass, config_entry)) == 3
    entity_entry = entity_entries(hass, config_entry)[
        f"{TEST_DEVICE_ID}_indoor_temperature"
    ]

    state = hass.states.get(entity_entry.entity_id)
    assert state is not None
    assert state.state == "21.0"

    await set_device_attribute(device, ACAttributes.indoor_temperature, 19.5)

    state = hass.states.get(entity_entry.entity_id)
    assert state is not None
    assert state.state == "19.5"

    entity_entry = entity_entries(hass, config_entry)[
        f"{TEST_DEVICE_ID}_outdoor_temperature"
    ]
    state = hass.states.get(entity_entry.entity_id)
    assert state is not None
    assert state.state == "unknown"

    entity_entry = entity_entries(hass, config_entry)[
        f"{TEST_DEVICE_ID}_indoor_humidity"
    ]
    state = hass.states.get(entity_entry.entity_id)
    assert state is not None
    assert state.state == "unknown"

    await set_device_attribute(device, ACAttributes.indoor_humidity, 255)
    state = hass.states.get(entity_entry.entity_id)
    assert state is not None
    assert state.state == "unknown"
