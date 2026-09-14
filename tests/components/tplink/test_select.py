"""Tests for tplink select platform."""

from kasa import Feature
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.tplink.const import DOMAIN
from homeassistant.components.tplink.entity import EXCLUDED_FEATURES
from homeassistant.components.tplink.select import SELECT_DESCRIPTIONS
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


@pytest.fixture
def mocked_feature_select() -> Feature:
    """Return mocked tplink select feature."""
    return _mocked_feature(
        "light_preset",
        value="First choice",
        name="light_preset",
        choices=["First choice", "Second choice"],
        type_=Feature.Type.Choice,
        category=Feature.Category.Config,
    )


async def test_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test select states."""
    features = {description.key for description in SELECT_DESCRIPTIONS}
    features.update(EXCLUDED_FEATURES)
    device = _mocked_device(alias="my_device", features=features)

    await setup_platform_for_device(hass, mock_config_entry, Platform.SELECT, device)
    await snapshot_platform(
        hass, entity_registry, device_registry, snapshot, mock_config_entry.entry_id
    )

    for excluded in EXCLUDED_FEATURES:
        assert hass.states.get(f"sensor.my_device_{excluded}") is None


async def test_select(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mocked_feature_select: Feature,
) -> None:
    """Test select unique ids."""
    mocked_feature = mocked_feature_select
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)

    plug = _mocked_device(alias="my_plug", features=[mocked_feature])
    with _patch_discovery(device=plug), _patch_connect(device=plug):
        await hass.config_entries.async_setup(already_migrated_config_entry.entry_id)
        await hass.async_block_till_done()

    # The entity_id is based on standard name from core.
    entity_id = "select.my_plug_light_preset"
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == f"{DEVICE_ID}_{mocked_feature.id}"


async def test_select_children(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mocked_feature_select: Feature,
) -> None:
    """Test select children."""
    mocked_feature = mocked_feature_select
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
        await hass.config_entries.async_setup(already_migrated_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "select.my_plug_light_preset"
    entity = entity_registry.async_get(entity_id)
    assert entity
    device = device_registry.async_get(entity.device_id)

    for plug_id in range(2):
        child_entity_id = f"select.my_plug_plug{plug_id}_light_preset"
        child_entity = entity_registry.async_get(child_entity_id)
        assert child_entity
        assert child_entity.unique_id == f"PLUG{plug_id}DEVICEID_{mocked_feature.id}"
        assert child_entity.device_id != entity.device_id
        child_device = device_registry.async_get(child_entity.device_id)
        assert child_device
        assert child_device.via_device_id == device.id


async def test_select_select(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mocked_feature_select: Feature,
) -> None:
    """Test a select setting values."""
    mocked_feature = mocked_feature_select
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    plug = _mocked_device(alias="my_plug", features=[mocked_feature])
    with _patch_discovery(device=plug), _patch_connect(device=plug):
        await hass.config_entries.async_setup(already_migrated_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "select.my_plug_light_preset"
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == f"{DEVICE_ID}_light_preset"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "Second choice"},
        blocking=True,
    )
    mocked_feature.set_value.assert_called_with("Second choice")
