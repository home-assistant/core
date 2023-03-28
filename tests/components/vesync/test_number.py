"""Tests for VeSync numbers."""
from unittest.mock import MagicMock, Mock, patch

import pytest

from homeassistant.components.vesync import DOMAIN, VS_NUMBERS
from homeassistant.components.vesync.common import VeSyncBaseEntity
from homeassistant.components.vesync.number import (
    MistLevelEntityDescriptionFactory,
    VeSyncNumberEntity,
    VeSyncNumberEntityDescription,
    WarmMistLevelEntityDescriptionFactory,
    async_setup_entry,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def test_async_setup_entry(
    hass: HomeAssistant,
    config_entry,
    humidifier: VeSyncBaseEntity,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the discovery mechanism can handle supported devices."""
    callback = Mock(AddEntitiesCallback)

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][VS_NUMBERS] = [humidifier]
    with patch.object(config_entry, "async_on_unload") as mock_on_unload:
        await async_setup_entry(hass, config_entry, callback)
        await hass.async_block_till_done()

    callback.assert_called_once()
    assert len(callback.call_args.args[0]) == 2
    assert callback.call_args.args[0][0].device == humidifier
    assert callback.call_args.args[0][1].device == humidifier
    assert callback.call_args.kwargs == {"update_before_add": True}
    mock_on_unload.assert_called_once()
    assert len(caplog.records) == 0


async def test_async_setup_entry__empty(
    hass: HomeAssistant, config_entry, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the discovery mechanism can handle no devices."""
    callback = Mock(AddEntitiesCallback)

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][VS_NUMBERS] = []
    with patch.object(config_entry, "async_on_unload") as mock_on_unload:
        await async_setup_entry(hass, config_entry, callback)
        await hass.async_block_till_done()

    callback.assert_called_once()
    assert callback.call_args.args == ([],)
    assert callback.call_args.kwargs == {"update_before_add": True}
    mock_on_unload.assert_called_once()
    assert len(caplog.records) == 0


async def test_async_setup_entry__invalid(
    hass: HomeAssistant, config_entry, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the discovery mechanism can handle unsupported devices."""
    mock_humidifier = MagicMock(VeSyncBaseEntity)
    mock_humidifier.device_type = "invalid_type"
    mock_humidifier.device_name = "invalid_name"
    details = {}
    mock_humidifier.details = details
    config_dict = {}
    mock_humidifier.config_dict = config_dict

    callback = Mock(AddEntitiesCallback)

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][VS_NUMBERS] = [mock_humidifier]
    with patch.object(config_entry, "async_on_unload") as mock_on_unload:
        await async_setup_entry(hass, config_entry, callback)
        await hass.async_block_till_done()

    callback.assert_called_once()
    assert callback.call_args.args == ([],)
    assert callback.call_args.kwargs == {"update_before_add": True}
    mock_on_unload.assert_called_once()
    assert caplog.messages[0] == "invalid_name - Unsupported device type - invalid_type"


async def test_number_entity__init(humidifier: VeSyncBaseEntity) -> None:
    """Test the number entity constructor."""
    mock_value_fn = Mock(return_value=5)
    mock_update_fn = Mock()
    description = VeSyncNumberEntityDescription(
        key="desc-key",
        name="Desc Name",
        value_fn=mock_value_fn,
        update_fn=mock_update_fn,
        native_min_value=1,
        native_max_value=10,
    )
    entity = VeSyncNumberEntity(humidifier, description)

    assert entity.device == humidifier
    assert entity.device_class is None
    assert entity.entity_category is None
    assert entity.entity_description == description
    assert entity.entity_picture is None
    assert entity.has_entity_name is False
    assert entity.icon is None
    assert entity.max_value == 10
    assert entity.min_value == 1
    assert entity.name == "device name Desc Name"
    assert entity.native_max_value == 10
    assert entity.native_min_value == 1
    assert entity.native_step is None
    assert entity.native_unit_of_measurement is None
    assert entity.step == 1.0
    assert entity.supported_features is None
    assert entity.unique_id == "cid1-desc-key"
    assert entity.unit_of_measurement is None
    mock_value_fn.assert_not_called()
    mock_update_fn.assert_not_called()


async def test_number_entity__native_value(humidifier: VeSyncBaseEntity) -> None:
    """Test the number entity native_value impl."""
    mock_value_fn = Mock(return_value=5)
    mock_update_fn = Mock()
    description = VeSyncNumberEntityDescription(
        key="desc-key",
        name="Desc Name",
        value_fn=mock_value_fn,
        update_fn=mock_update_fn,
        native_min_value=1,
        native_max_value=10,
    )
    entity = VeSyncNumberEntity(humidifier, description)
    assert entity.native_value == 5
    mock_value_fn.assert_called_once()
    mock_update_fn.assert_not_called()


async def test_number_entity__set_native_value(humidifier: VeSyncBaseEntity) -> None:
    """Test the number entity set_native_value impl."""
    mock_value_fn = Mock(return_value=5)
    mock_update_fn = Mock()
    description = VeSyncNumberEntityDescription(
        key="desc-key",
        name="Desc Name",
        value_fn=mock_value_fn,
        update_fn=mock_update_fn,
        native_min_value=1,
        native_max_value=10,
    )
    entity = VeSyncNumberEntity(humidifier, description)
    entity.set_native_value(9)
    mock_value_fn.assert_not_called()
    mock_update_fn.assert_called_once()


async def test_mist_level_factory__create() -> None:
    """Test the Mist Level Factory create impl."""
    factory = MistLevelEntityDescriptionFactory()

    device = MagicMock(VeSyncBaseEntity)
    details_dict = {"mist_virtual_level": 1}
    device.details = MagicMock()
    device.details.__getitem__.side_effect = details_dict.__getitem__
    device.config_dict = {"mist_levels": ["1", "2"]}
    device.set_mist_level = Mock()

    description = factory.create(device)
    assert description
    assert description.key == "mist-level"
    assert description.name == "Mist Level"
    assert description.entity_category == EntityCategory.CONFIG
    assert description.native_step == 1
    assert description.native_min_value == 1.0
    assert description.native_max_value == 2.0
    assert callable(description.value_fn)
    assert description.value_fn(device) == 1
    assert device.details.mock_calls[0].args == ("mist_virtual_level",)
    assert callable(description.update_fn)
    description.update_fn(device, 2)
    device.set_mist_level.assert_called_once_with(2)


async def test_mist_level_factory__supports() -> None:
    """Test the Mist Level Factory supports impl."""
    factory = MistLevelEntityDescriptionFactory()

    device = MagicMock(VeSyncBaseEntity)
    device.set_mist_level = None
    assert factory.supports(device) is False
    device.set_mist_level = Mock()
    assert factory.supports(device) is True


async def test_warm_mist_level_factory__create() -> None:
    """Test the Warm Mist Level Factory creates impl."""
    factory = WarmMistLevelEntityDescriptionFactory()

    device = MagicMock(VeSyncBaseEntity)
    details_dict = {"warm_mist_level": 1}
    device.details = MagicMock()
    device.details.__getitem__.side_effect = details_dict.__getitem__
    device.config_dict = {"warm_mist_levels": ["1", "2"]}
    device.set_warm_level = Mock()

    description = factory.create(device)
    assert description
    assert description.key == "warm-mist-level"
    assert description.name == "Warm Mist Level"
    assert description.entity_category == EntityCategory.CONFIG
    assert description.native_step == 1
    assert description.native_min_value == 1.0
    assert description.native_max_value == 2.0
    assert callable(description.value_fn)
    assert description.value_fn(device) == 1
    assert device.details.mock_calls[0].args == ("warm_mist_level",)
    assert callable(description.update_fn)
    description.update_fn(device, 2)
    device.set_warm_level.assert_called_once_with(2)


async def test_warm_mist_level_factory__supports() -> None:
    """Test the Warm Mist Level Factory supports impl."""
    factory = WarmMistLevelEntityDescriptionFactory()

    device = MagicMock(VeSyncBaseEntity)
    assert factory.supports(device) is False
    device.warm_mist_feature = False
    device.details = {}
    assert factory.supports(device) is False
    device.warm_mist_feature = True
    device.details["mist_virtual_level"] = 1
    assert factory.supports(device) is True
