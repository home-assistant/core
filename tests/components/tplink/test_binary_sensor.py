"""Tests for tplink binary_sensor platform."""

from kasa import Feature
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
    _mocked_feature,
    _mocked_strip_children,
    _patch_connect,
    _patch_discovery,
)

from tests.common import MockConfigEntry


@pytest.fixture
def mocked_feature_binary_sensor() -> Feature:
    """Return mocked tplink binary sensor feature."""
    return _mocked_feature(
        False,
        "overheated",
        name="Overheated",
        type_=Feature.Type.BinarySensor,
        category=Feature.Category.Primary,
    )


async def test_binary_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mocked_feature_binary_sensor: Feature,
) -> None:
    """Test a sensor unique ids."""
    mocked_feature = mocked_feature_binary_sensor
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)

    plug = _mocked_device(alias="my_plug", features=[mocked_feature])
    with _patch_discovery(device=plug), _patch_connect(device=plug):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    # The entity_id is based on standard name from core.
    entity_id = "binary_sensor.my_plug_heat"
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == f"{DEVICE_ID}_{mocked_feature.id}"


async def test_binary_sensor_children(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mocked_feature_binary_sensor: Feature,
) -> None:
    """Test a sensor unique ids."""
    mocked_feature = mocked_feature_binary_sensor
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    plug = _mocked_device(
        alias="my_plug",
        features=[mocked_feature],
        children=_mocked_strip_children(features=[mocked_feature]),
    )
    with _patch_discovery(device=plug), _patch_connect(device=plug):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "binary_sensor.my_plug_heat"
    entity = entity_registry.async_get(entity_id)
    assert entity
    device = device_registry.async_get(entity.device_id)

    for plug_id in range(2):
        child_entity_id = f"binary_sensor.my_plug_plug{plug_id}_heat"
        child_entity = entity_registry.async_get(child_entity_id)
        assert child_entity
        assert child_entity.unique_id == f"PLUG{plug_id}DEVICEID_{mocked_feature.id}"
        assert child_entity.device_id != entity.device_id
        child_device = device_registry.async_get(child_entity.device_id)
        assert child_device
        assert child_device.via_device_id == device.id
