"""Tests for light platform."""

from kasa import Device, Feature, Module
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import tplink
from homeassistant.components.tplink.const import DOMAIN
from homeassistant.components.tplink.entity import EXCLUDED_FEATURES
from homeassistant.components.tplink.sensor import SENSOR_DESCRIPTIONS
from homeassistant.const import CONF_HOST, Platform
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
    setup_platform_for_device,
    snapshot_platform,
)

from tests.common import MockConfigEntry


async def test_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test a sensor unique ids."""
    features = {description.key for description in SENSOR_DESCRIPTIONS}
    features.update(EXCLUDED_FEATURES)
    device = _mocked_device(alias="my_device", features=features)

    await setup_platform_for_device(hass, mock_config_entry, Platform.SENSOR, device)
    await snapshot_platform(
        hass, entity_registry, device_registry, snapshot, mock_config_entry.entry_id
    )

    for excluded in EXCLUDED_FEATURES:
        assert hass.states.get(f"sensor.my_device_{excluded}") is None


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


async def test_undefined_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a message is logged when discovering a feature without a description."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    new_feature = _mocked_feature(
        "consumption_this_fortnight",
        value=5.2,
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

    msg = (
        "Device feature: Consumption for fortnight (consumption_this_fortnight) "
        "needs an entity description defined in HA"
    )
    assert msg in caplog.text


async def test_sensor_children_on_parent(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a WallSwitch sensor entities are added to parent."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    feature = _mocked_feature(
        "consumption_this_month",
        value=5.2,
        # integration should ignore name and use the value from strings.json:
        # This month's consumption
        name="Consumption for month",
        type_=Feature.Type.Sensor,
        category=Feature.Category.Primary,
        unit="A",
        precision_hint=2,
    )
    plug = _mocked_device(
        alias="my_plug",
        features=[feature],
        children=_mocked_strip_children(features=[feature]),
        device_type=Device.Type.WallSwitch,
    )
    with _patch_discovery(device=plug), _patch_connect(device=plug):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "sensor.my_plug_this_month_s_consumption"
    entity = entity_registry.async_get(entity_id)
    assert entity
    device = device_registry.async_get(entity.device_id)

    for plug_id in range(2):
        child_entity_id = f"sensor.my_plug_plug{plug_id}_this_month_s_consumption"
        child_entity = entity_registry.async_get(child_entity_id)
        assert child_entity
        assert child_entity.unique_id == f"PLUG{plug_id}DEVICEID_consumption_this_month"
        child_device = device_registry.async_get(child_entity.device_id)
        assert child_device

        assert child_entity.device_id == entity.device_id
        assert child_device.connections == device.connections


async def test_sensor_children_on_child(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test strip sensors are on child device."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    feature = _mocked_feature(
        "consumption_this_month",
        value=5.2,
        # integration should ignore name and use the value from strings.json:
        # This month's consumption
        name="Consumption for month",
        type_=Feature.Type.Sensor,
        category=Feature.Category.Primary,
        unit="A",
        precision_hint=2,
    )
    plug = _mocked_device(
        alias="my_plug",
        features=[feature],
        children=_mocked_strip_children(features=[feature]),
        device_type=Device.Type.Strip,
    )
    with _patch_discovery(device=plug), _patch_connect(device=plug):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "sensor.my_plug_this_month_s_consumption"
    entity = entity_registry.async_get(entity_id)
    assert entity
    device = device_registry.async_get(entity.device_id)

    for plug_id in range(2):
        child_entity_id = f"sensor.my_plug_plug{plug_id}_this_month_s_consumption"
        child_entity = entity_registry.async_get(child_entity_id)
        assert child_entity
        assert child_entity.unique_id == f"PLUG{plug_id}DEVICEID_consumption_this_month"
        child_device = device_registry.async_get(child_entity.device_id)
        assert child_device

        assert child_entity.device_id != entity.device_id
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
