"""Tests for light platform."""

from kasa import Feature, Module
import pytest

from homeassistant.components import tplink
from homeassistant.components.tplink.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from . import (
    DEVICE_ID,
    MAC_ADDRESS,
    _mocked_device,
    _mocked_energy_features,
    _mocked_feature,
    _mocked_strip_children,
    _patch_connect,
    _patch_discovery,
)

from tests.common import MockConfigEntry


async def test_color_light_with_an_emeter(hass: HomeAssistant) -> None:
    """Test a light with an emeter."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    emeter_features = _mocked_energy_features(
        power=None,
        total=None,
        voltage=None,
        current=5,
        today=5000.0036,
    )
    bulb = _mocked_device(
        alias="my_bulb", modules=[Module.Light], features=["state", *emeter_features]
    )
    with _patch_discovery(device=bulb), _patch_connect(device=bulb):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()
        await hass.async_block_till_done()

    expected = {
        "sensor.my_bulb_today_s_consumption": 5000.004,
        "sensor.my_bulb_current": 5,
    }
    entity_id = "light.my_bulb"
    state = hass.states.get(entity_id)
    assert state.state == "on"
    for sensor_entity_id, value in expected.items():
        assert hass.states.get(sensor_entity_id).state == str(value)

    not_expected = {
        "sensor.my_bulb_current_consumption",
        "sensor.my_bulb_total_consumption",
        "sensor.my_bulb_voltage",
    }
    for sensor_entity_id in not_expected:
        assert hass.states.get(sensor_entity_id) is None


async def test_plug_with_an_emeter(hass: HomeAssistant) -> None:
    """Test a plug with an emeter."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    emeter_features = _mocked_energy_features(
        power=100.06,
        total=30.0049,
        voltage=121.19,
        current=5.035,
    )
    plug = _mocked_device(alias="my_plug", features=["state", *emeter_features])
    with _patch_discovery(device=plug), _patch_connect(device=plug):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()
        await hass.async_block_till_done()

    expected = {
        "sensor.my_plug_current_consumption": 100.1,
        "sensor.my_plug_total_consumption": 30.005,
        "sensor.my_plug_today_s_consumption": 0.0,
        "sensor.my_plug_voltage": 121.2,
        "sensor.my_plug_current": 5.04,
    }
    entity_id = "switch.my_plug"
    state = hass.states.get(entity_id)
    assert state.state == "on"
    for sensor_entity_id, value in expected.items():
        assert hass.states.get(sensor_entity_id).state == str(value)


async def test_color_light_no_emeter(hass: HomeAssistant) -> None:
    """Test a light without an emeter."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb = _mocked_device(alias="my_bulb", modules=[Module.Light])
    bulb.has_emeter = False
    with _patch_discovery(device=bulb), _patch_connect(device=bulb):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"
    state = hass.states.get(entity_id)
    assert state.state == "on"

    not_expected = [
        "sensor.my_bulb_current_consumption"
        "sensor.my_bulb_total_consumption"
        "sensor.my_bulb_today_s_consumption"
        "sensor.my_bulb_voltage"
        "sensor.my_bulb_current"
    ]
    for sensor_entity_id in not_expected:
        assert hass.states.get(sensor_entity_id) is None


async def test_sensor_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a sensor unique ids."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    emeter_features = _mocked_energy_features(
        power=100,
        total=30,
        voltage=121,
        current=5,
        today=None,
    )
    plug = _mocked_device(alias="my_plug", features=emeter_features)
    with _patch_discovery(device=plug), _patch_connect(device=plug):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    expected = {
        "sensor.my_plug_current_consumption": f"{DEVICE_ID}_current_power_w",
        "sensor.my_plug_total_consumption": f"{DEVICE_ID}_total_energy_kwh",
        "sensor.my_plug_today_s_consumption": f"{DEVICE_ID}_today_energy_kwh",
        "sensor.my_plug_voltage": f"{DEVICE_ID}_voltage",
        "sensor.my_plug_current": f"{DEVICE_ID}_current_a",
    }
    for sensor_entity_id, value in expected.items():
        assert entity_registry.async_get(sensor_entity_id).unique_id == value


async def test_new_sensor(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a sensor unique ids."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    new_feature = _mocked_feature(
        5.2,
        "consumption_this_fortnight",
        name="Consumption for fortnight",
        type_=Feature.Type.Sensor,
        category=Feature.Category.Primary,
        unit="A",
        precision_hint=2,
    )
    plug = _mocked_device(alias="my_plug", features=[new_feature])
    with _patch_discovery(device=plug), _patch_connect(device=plug):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "sensor.my_plug_consumption_for_fortnight"
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == f"{DEVICE_ID}_consumption_this_fortnight"


async def test_sensor_children(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a sensor unique ids."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    new_feature = _mocked_feature(
        5.2,
        "consumption_this_fortnight",
        name="Consumption for fortnight",
        type_=Feature.Type.Sensor,
        category=Feature.Category.Primary,
        unit="A",
        precision_hint=2,
    )
    plug = _mocked_device(
        alias="my_plug",
        features=[new_feature],
        children=_mocked_strip_children(features=[new_feature]),
    )
    with _patch_discovery(device=plug), _patch_connect(device=plug):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "sensor.my_plug_consumption_for_fortnight"
    entity = entity_registry.async_get(entity_id)
    assert entity
    device = device_registry.async_get(entity.device_id)

    for plug_id in range(2):
        child_entity_id = f"sensor.my_plug_plug{plug_id}_consumption_for_fortnight"
        child_entity = entity_registry.async_get(child_entity_id)
        assert child_entity
        assert (
            child_entity.unique_id
            == f"PLUG{plug_id}DEVICEID_consumption_this_fortnight"
        )
        assert child_entity.device_id != entity.device_id
        child_device = device_registry.async_get(child_entity.device_id)
        assert child_device
        assert child_device.via_device_id == device.id


@pytest.mark.skip
async def test_new_datetime_sensor(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a sensor unique ids."""
    # Skipped temporarily while datetime handling on hold.
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    plug = _mocked_device(alias="my_plug", features=["on_since"])
    with _patch_discovery(device=plug), _patch_connect(device=plug):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "sensor.my_plug_on_since"
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == f"{DEVICE_ID}_on_since"
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["device_class"] == "timestamp"
