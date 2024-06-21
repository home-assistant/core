"""Tests for tplink binary_sensor platform."""

from kasa import Feature

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


async def test_binary_sensor_unique_id(
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


async def test_binary_sensor(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a sensor unique ids."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    new_feature = _mocked_feature(
        False,
        "some_binary_sensor",
        name="Some binary sensor",
        type_=Feature.Type.BinarySensor,
        category=Feature.Category.Primary,
    )
    plug = _mocked_device(alias="my_plug", features=[new_feature])
    with _patch_discovery(device=plug), _patch_connect(device=plug):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "binary_sensor.my_plug_some_binary_sensor"
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == f"{DEVICE_ID}_some_binary_sensor"


async def test_binary_sensor_children(
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
        False,
        "some_binary_sensor",
        name="Some binary sensor",
        type_=Feature.Type.BinarySensor,
        category=Feature.Category.Primary,
    )
    plug = _mocked_device(
        alias="my_plug",
        features=[new_feature],
        children=_mocked_strip_children(features=[new_feature]),
    )
    with _patch_discovery(device=plug), _patch_connect(device=plug):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "binary_sensor.my_plug_some_binary_sensor"
    entity = entity_registry.async_get(entity_id)
    assert entity
    device = device_registry.async_get(entity.device_id)

    for plug_id in range(2):
        child_entity_id = f"binary_sensor.my_plug_plug{plug_id}_some_binary_sensor"
        child_entity = entity_registry.async_get(child_entity_id)
        assert child_entity
        assert child_entity.unique_id == f"PLUG{plug_id}DEVICEID_some_binary_sensor"
        assert child_entity.device_id != entity.device_id
        child_device = device_registry.async_get(child_entity.device_id)
        assert child_device
        assert child_device.via_device_id == device.id
