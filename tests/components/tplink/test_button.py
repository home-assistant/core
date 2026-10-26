"""Tests for tplink button platform."""

from kasa import Feature
import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.tplink.button import BUTTON_DESCRIPTIONS
from homeassistant.components.tplink.entity import EXCLUDED_FEATURES
from homeassistant.const import ATTR_ENTITY_ID, Platform
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
from .const import DEVICE_ID


@pytest.fixture
def mocked_feature_button() -> Feature:
    """Return mocked tplink button feature."""
    return _mocked_feature(
        "reboot",
        value="<Action>",
        name="Reboot",
        type_=Feature.Type.Action,
        category=Feature.Category.Primary,
    )


async def test_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test button states."""
    features = {description.key for description in BUTTON_DESCRIPTIONS}
    features.update(EXCLUDED_FEATURES)
    device = _mocked_device(alias="my_device", features=features)

    await setup_platform_for_device(hass, mock_config_entry, Platform.BUTTON, device)
    await snapshot_platform(
        hass, entity_registry, device_registry, snapshot, mock_config_entry.entry_id
    )

    for excluded in EXCLUDED_FEATURES:
        assert hass.states.get(f"sensor.my_device_{excluded}") is None


async def test_button(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mocked_feature_button: Feature,
) -> None:
    """Test button unique ids."""
    mocked_feature = mocked_feature_button
    plug = _mocked_device(alias="my_device", features=[mocked_feature])
    mock_config_entry.add_to_hass(hass)
    with _patch_discovery(device=plug), _patch_connect(device=plug):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # The entity_id is based on standard name from core.
    entity_id = "button.my_device_restart"
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == f"{DEVICE_ID}_{mocked_feature.id}"


async def test_button_children(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mocked_feature_button: Feature,
) -> None:
    """Test button children."""
    mocked_feature = mocked_feature_button
    plug = _mocked_device(
        alias="my_device",
        features=[mocked_feature],
        children=_mocked_strip_children(features=[mocked_feature]),
    )
    mock_config_entry.add_to_hass(hass)
    with _patch_discovery(device=plug), _patch_connect(device=plug):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "button.my_device_restart"
    entity = entity_registry.async_get(entity_id)
    assert entity
    device = device_registry.async_get(entity.device_id)

    for plug_id in range(2):
        child_entity_id = f"button.my_device_plug{plug_id}_restart"
        child_entity = entity_registry.async_get(child_entity_id)
        assert child_entity
        assert child_entity.unique_id == f"PLUG{plug_id}DEVICEID_{mocked_feature.id}"
        assert child_entity.device_id != entity.device_id
        child_device = device_registry.async_get(child_entity.device_id)
        assert child_device
        assert child_device.via_device_id == device.id


async def test_button_press(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mocked_feature_button: Feature,
) -> None:
    """Test a number entity limits and setting values."""
    mocked_feature = mocked_feature_button
    plug = _mocked_device(alias="my_device", features=[mocked_feature])
    mock_config_entry.add_to_hass(hass)
    with _patch_discovery(device=plug), _patch_connect(device=plug):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "button.my_device_restart"
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == f"{DEVICE_ID}_reboot"

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mocked_feature.set_value.assert_called_with(True)
