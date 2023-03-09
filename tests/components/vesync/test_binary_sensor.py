"""Tests for VeSync numbers."""
from unittest.mock import MagicMock, Mock, patch

import pytest

from homeassistant.components.vesync.binary_sensor import (
    DOMAIN,
    VS_BINARY_SENSORS,
    EmptyWaterTankEntityDescriptionFactory,
    HighHumidityEntityDescriptionFactory,
    VeSyncBinarySensorEntity,
    VeSyncBinarySensorEntityDescription,
    WaterTankLiftedEntityDescriptionFactory,
    async_setup_entry,
)
from homeassistant.components.vesync.common import VeSyncBaseEntity
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
    hass.data[DOMAIN][VS_BINARY_SENSORS] = [humidifier]
    with patch.object(config_entry, "async_on_unload") as mock_on_unload:
        await async_setup_entry(hass, config_entry, callback)
        await hass.async_block_till_done()

    callback.assert_called_once()
    assert len(callback.call_args.args[0]) == 3
    assert callback.call_args.args[0][0].device == humidifier
    assert callback.call_args.args[0][1].device == humidifier
    assert callback.call_args.args[0][2].device == humidifier
    assert callback.call_args.kwargs == {"update_before_add": True}
    mock_on_unload.assert_called_once()
    assert len(caplog.records) == 0


async def test_async_setup_entry__empty(
    hass: HomeAssistant, config_entry, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the discovery mechanism can handle no devices."""
    callback = Mock(AddEntitiesCallback)

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][VS_BINARY_SENSORS] = []
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

    callback = Mock(AddEntitiesCallback)

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][VS_BINARY_SENSORS] = [mock_humidifier]
    with patch.object(config_entry, "async_on_unload") as mock_on_unload:
        await async_setup_entry(hass, config_entry, callback)
        await hass.async_block_till_done()

    callback.assert_called_once()
    assert callback.call_args.args == ([],)
    assert callback.call_args.kwargs == {"update_before_add": True}
    mock_on_unload.assert_called_once()
    assert caplog.messages[0] == "invalid_name - Unsupported device type - invalid_type"


async def test_binary_sensor_entity__init(humidifier: VeSyncBaseEntity) -> None:
    """Test the number entity constructor."""
    mock_value_fn = Mock(return_value=True)
    description = VeSyncBinarySensorEntityDescription(
        key="desc-key",
        name="Desc Name",
        value_fn=mock_value_fn,
    )
    entity = VeSyncBinarySensorEntity(humidifier, description)

    assert entity.device == humidifier
    assert entity.device_class is None
    assert entity.entity_category is None
    assert entity.entity_description == description
    assert entity.entity_picture is None
    assert entity.has_entity_name is False
    assert entity.icon is None
    assert entity.name == "device name Desc Name"
    assert entity.supported_features is None
    assert entity.unique_id == "cid1-desc-key"
    mock_value_fn.assert_not_called()


async def test_binary_sensor_entity__is_on(humidifier: VeSyncBaseEntity) -> None:
    """Test the number entity native_value impl."""
    mock_value_fn = Mock(return_value=True)
    description = VeSyncBinarySensorEntityDescription(
        key="desc-key",
        name="Desc Name",
        value_fn=mock_value_fn,
    )
    entity = VeSyncBinarySensorEntity(humidifier, description)
    assert entity.is_on is True
    mock_value_fn.assert_called_once()


async def test_empty_tank_factory__create() -> None:
    """Test the Empty Water Tank Factory supports impl."""
    factory = EmptyWaterTankEntityDescriptionFactory()

    device = MagicMock(VeSyncBaseEntity)
    details_dict = {"water_lacks": True}
    device.details = MagicMock()
    device.details.get.side_effect = details_dict.get
    device.details.__getitem__.side_effect = details_dict.__getitem__

    description = factory.create(device)
    assert description
    assert description.key == "water_lacks"
    assert description.name == "Empty Water Tank"
    assert description.icon == "mdi:water-alert"
    assert description.entity_category == EntityCategory.DIAGNOSTIC
    assert callable(description.value_fn)
    assert description.value_fn(device) is True
    assert device.details.mock_calls[0].args == ("water_lacks", None)


async def test_empty_tank_factory__supports() -> None:
    """Test the Empty Water Tank Factory supports impl."""
    factory = EmptyWaterTankEntityDescriptionFactory()

    device = MagicMock(VeSyncBaseEntity)
    device.details = {}
    assert factory.supports(device) is False
    device.details["water_lacks"] = True
    assert factory.supports(device) is True


async def test_tank_lifted_factory__create() -> None:
    """Test the Water Tank Lifted Factory supports impl."""
    factory = WaterTankLiftedEntityDescriptionFactory()

    device = MagicMock(VeSyncBaseEntity)
    details_dict = {"water_tank_lifted": True}
    device.details = MagicMock()
    device.details.get.side_effect = details_dict.get
    device.details.__getitem__.side_effect = details_dict.__getitem__

    description = factory.create(device)
    assert description
    assert description.key == "water_tank_lifted"
    assert description.name == "Water Tank Lifted"
    assert description.icon == "mdi:water-alert"
    assert description.entity_category == EntityCategory.DIAGNOSTIC
    assert callable(description.value_fn)
    assert description.value_fn(device) is True
    assert device.details.mock_calls[0].args == ("water_tank_lifted", None)


async def test_tank_lifted_factory__supports() -> None:
    """Test the Water Tank Lifted Factory supports impl."""
    factory = WaterTankLiftedEntityDescriptionFactory()

    device = MagicMock(VeSyncBaseEntity)
    device.details = {}
    assert factory.supports(device) is False
    device.details["water_tank_lifted"] = True
    assert factory.supports(device) is True


async def test_high_humidity_factory__create() -> None:
    """Test the High Humidity Factory supports impl."""
    factory = HighHumidityEntityDescriptionFactory()

    device = MagicMock(VeSyncBaseEntity)
    details_dict = {"humidity_high": True}
    device.details = MagicMock()
    device.details.get.side_effect = details_dict.get
    device.details.__getitem__.side_effect = details_dict.__getitem__

    description = factory.create(device)
    assert description
    assert description.key == "humidity_high"
    assert description.name == "Humidity High"
    assert description.icon == "mdi:water-percent-alert"
    assert description.entity_category == EntityCategory.DIAGNOSTIC
    assert callable(description.value_fn)
    assert description.value_fn(device) is True
    assert device.details.mock_calls[0].args == ("humidity_high", None)


async def test_high_humidity_factory__supports() -> None:
    """Test the High Humidity Factory supports impl."""
    factory = HighHumidityEntityDescriptionFactory()

    device = MagicMock(VeSyncBaseEntity)
    device.details = {}
    assert factory.supports(device) is False
    device.details["humidity_high"] = True
    assert factory.supports(device) is True
