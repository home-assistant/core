"""Tests for tplink number platform."""

from kasa import Feature
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.tplink.const import DOMAIN
from homeassistant.components.tplink.entity import EXCLUDED_FEATURES
from homeassistant.components.tplink.number import NUMBER_DESCRIPTIONS
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import (
    _mocked_device,
    _mocked_feature,
    _mocked_strip_children,
    _patch_connect,
    _patch_discovery,
    setup_platform_for_device,
    snapshot_platform,
)
from .const import DEVICE_ID, MAC_ADDRESS

from tests.common import MockConfigEntry


async def test_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test a number states."""
    features = {description.key for description in NUMBER_DESCRIPTIONS}
    features.update(EXCLUDED_FEATURES)
    device = _mocked_device(alias="my_device", features=features)

    await setup_platform_for_device(hass, mock_config_entry, Platform.NUMBER, device)
    await snapshot_platform(
        hass, entity_registry, device_registry, snapshot, mock_config_entry.entry_id
    )

    for excluded in EXCLUDED_FEATURES:
        assert hass.states.get(f"sensor.my_device_{excluded}") is None


async def test_number(hass: HomeAssistant, entity_registry: er.EntityRegistry) -> None:
    """Test number unique ids."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    new_feature = _mocked_feature(
        "temperature_offset",
        value=10,
        name="Temperature offset",
        type_=Feature.Type.Number,
        category=Feature.Category.Config,
        minimum_value=1,
        maximum_value=100,
    )
    plug = _mocked_device(alias="my_plug", features=[new_feature])
    with _patch_discovery(device=plug), _patch_connect(device=plug):
        await hass.config_entries.async_setup(already_migrated_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "number.my_plug_temperature_offset"
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == f"{DEVICE_ID}_temperature_offset"


async def test_number_children(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test number children."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    new_feature = _mocked_feature(
        "temperature_offset",
        value=10,
        name="Some number",
        type_=Feature.Type.Number,
        category=Feature.Category.Config,
        minimum_value=1,
        maximum_value=100,
    )
    plug = _mocked_device(
        alias="my_plug",
        features=[new_feature],
        children=_mocked_strip_children(features=[new_feature]),
    )
    with _patch_discovery(device=plug), _patch_connect(device=plug):
        await hass.config_entries.async_setup(already_migrated_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "number.my_plug_temperature_offset"
    entity = entity_registry.async_get(entity_id)
    assert entity
    device = device_registry.async_get(entity.device_id)

    for plug_id in range(2):
        child_entity_id = f"number.my_plug_plug{plug_id}_temperature_offset"
        child_entity = entity_registry.async_get(child_entity_id)
        assert child_entity
        assert child_entity.unique_id == f"PLUG{plug_id}DEVICEID_temperature_offset"
        assert child_entity.device_id != entity.device_id
        child_device = device_registry.async_get(child_entity.device_id)
        assert child_device
        assert child_device.via_device_id == device.id


async def test_number_set(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a number entity limits and setting values."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    new_feature = _mocked_feature(
        "temperature_offset",
        value=10,
        name="Some number",
        type_=Feature.Type.Number,
        category=Feature.Category.Config,
        minimum_value=1,
        maximum_value=200,
    )
    plug = _mocked_device(alias="my_plug", features=[new_feature])
    with _patch_discovery(device=plug), _patch_connect(device=plug):
        await hass.config_entries.async_setup(already_migrated_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "number.my_plug_temperature_offset"
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == f"{DEVICE_ID}_temperature_offset"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "10"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 50},
        blocking=True,
    )
    new_feature.set_value.assert_called_with(50)
