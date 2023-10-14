"""Test Browan sensor entity."""
import datetime
import json
import logging
from types import MappingProxyType
from unittest.mock import ANY, AsyncMock, Mock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.browan.devices import HassTBMS100
from homeassistant.components.browan.sensor import (
    _LOGGER as DUT_LOGGER,
    ENTITY_DESCRIPTIONS,
    BrowanSensorEntityDescription,
    LorawanSensorCoordinator,
    LorawanSensorEntity,
    async_setup_entry,
)
from homeassistant.components.mqtt.models import ReceiveMessage
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant

from .data import ttn_uplink  # noqa: F401


@pytest.fixture
def description_temperature():
    """Fixture to select temperature sensor description."""
    return [
        description
        for description in ENTITY_DESCRIPTIONS
        if description.key == ATTR_TEMPERATURE
    ][0]


@patch(
    "homeassistant.components.browan.sensor.LorawanSensorCoordinator.subscribe",
)
@pytest.mark.asyncio
async def test_async_setup_entry(
    mock_subscribe: AsyncMock,
    hass: HomeAssistant,
    mock_config_entry: config_entries.ConfigEntry,
    caplog_debug: pytest.LogCaptureFixture,
) -> None:
    """Test Browan sensor entity setup."""
    async_add_entities = Mock(autospec=True)

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    mock_subscribe.assert_called_once_with()
    assert len(async_add_entities.call_args_list[0].args[0]) == len(
        HassTBMS100.supported_sensors()
    )
    for entity in async_add_entities.call_args_list[0].args[0]:
        assert type(entity) == LorawanSensorEntity

    assert caplog_debug.record_tuples == []


@patch(
    "homeassistant.components.browan.sensor.LorawanSensorCoordinator.subscribe",
)
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("config_data", "warning_message"),
    [
        (
            {
                "model": "TEST-INVALID-DEVICE",
            },
            'Device name "TEST-INVALID-DEVICE" from Browan is invalid',
        ),
        (
            {
                "model": "testUnknownDevice",
            },
            'Device "testUnknownDevice" from Browan is unknown',
        ),
    ],
)
async def test_async_setup_invalid_device_name(
    mock_subscribe: AsyncMock,
    hass: HomeAssistant,
    mock_config_entry: config_entries.ConfigEntry,
    caplog_debug: pytest.LogCaptureFixture,
    config_data: dict,
    warning_message: str,
) -> None:
    """Test Browan sensor entity setup."""
    async_add_entities = Mock(autospec=True)
    mock_config_entry.data = MappingProxyType(config_data)

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    mock_subscribe.assert_not_called()

    assert caplog_debug.record_tuples == [
        (
            "homeassistant.components.browan.sensor",
            logging.ERROR,
            warning_message,
        ),
    ]


@patch("homeassistant.helpers.update_coordinator.DataUpdateCoordinator.__init__")
def test_lorawansensorcoordinator_constructor(
    mock_coordinator_constructor: AsyncMock,
    hass: HomeAssistant,
    mock_config_entry: config_entries.ConfigEntry,
    caplog_debug: pytest.LogCaptureFixture,
) -> None:
    """Test LoRaWAN sensor entity coordinator constructor."""
    LorawanSensorCoordinator(hass, mock_config_entry, HassTBMS100.parse_uplink)
    mock_coordinator_constructor.assert_called_once_with(
        hass, DUT_LOGGER, name="LorawanSensorCoordinator.TEST-ENTRY-TITLE"
    )

    assert caplog_debug.record_tuples == []


@pytest.mark.asyncio
async def test_lorawansensorcoordinator_subscribe(
    hass: HomeAssistant,
    mock_config_entry: config_entries.ConfigEntry,
    caplog_debug: pytest.LogCaptureFixture,
) -> None:
    """Test LoRaWAN sensor entity coordinator subscription to MQTT."""
    coordinator = LorawanSensorCoordinator(
        hass, mock_config_entry, HassTBMS100.parse_uplink
    )

    with patch.object(hass.components.mqtt, "async_subscribe") as mock_async_subscribe:
        await coordinator.subscribe()
        mock_async_subscribe.assert_awaited_once_with(
            "v3/+/devices/TEST-ENTRY-TITLE/up", ANY
        )

    assert caplog_debug.record_tuples == []


@pytest.mark.asyncio
async def test_lorawansensorcoordinator_subscribe_callback(
    hass: HomeAssistant,
    mock_config_entry: config_entries.ConfigEntry,
    caplog_debug: pytest.LogCaptureFixture,
    ttn_uplink: dict,  # noqa: F811
) -> None:
    """Test LoRaWAN sensor entity coordinator MQTT callback."""
    coordinator = LorawanSensorCoordinator(
        hass, mock_config_entry, HassTBMS100.parse_uplink
    )
    msg = ReceiveMessage(
        "TEST-TOPIC",
        json.dumps(ttn_uplink),
        0,
        False,
        "+",
        datetime.datetime.fromtimestamp(0),
    )
    await coordinator._message_received(msg)
    await hass.async_block_till_done()

    with patch.object(
        coordinator, "async_set_updated_data"
    ) as mock_async_set_updated_data:
        msg = ReceiveMessage(
            "TEST-TOPIC",
            json.dumps(ttn_uplink),
            0,
            False,
            "+",
            datetime.datetime.fromtimestamp(0),
        )
        await coordinator._message_received(msg)
        await hass.async_block_till_done()
        mock_async_set_updated_data.assert_called_once()

        assert (
            mock_async_set_updated_data.call_args_list[0].args[0].sensors.temperature
            == 23
        )

    assert caplog_debug.record_tuples == [
        (
            "homeassistant.components.browan.sensor",
            logging.DEBUG,
            "Manually updated LorawanSensorCoordinator.TEST-ENTRY-TITLE data",
        ),
    ]


def test_lorawan_sensor_entity_constructor(
    hass: HomeAssistant,
    mock_config_entry: config_entries.ConfigEntry,
    description_temperature: BrowanSensorEntityDescription,
    caplog_debug: pytest.LogCaptureFixture,
) -> None:
    """Test LoRaWAN sensor entity constructor."""
    coordinator = LorawanSensorCoordinator(
        hass, mock_config_entry, HassTBMS100.parse_uplink
    )
    entity = LorawanSensorEntity(
        hass, mock_config_entry, coordinator, description_temperature
    )

    assert entity._attr_has_entity_name is True
    assert entity._attr_state_class == SensorStateClass.MEASUREMENT
    assert entity._attr_unique_id == "0011223344556677_temperature"
    assert entity._config == mock_config_entry
    assert entity._hass == hass
    assert entity._sensor_data_key == description_temperature.key
    assert entity.coordinator == coordinator


@pytest.mark.asyncio
async def test_lorawan_sensor_entity_handle_update(
    hass: HomeAssistant,
    mock_config_entry: config_entries.ConfigEntry,
    description_temperature: BrowanSensorEntityDescription,
    caplog_debug: pytest.LogCaptureFixture,
    ttn_uplink: dict,  # noqa: F811
) -> None:
    """Test LoRaWAN sensor entity update from coordinator."""
    coordinator = LorawanSensorCoordinator(
        hass, mock_config_entry, HassTBMS100.parse_uplink
    )
    entity = LorawanSensorEntity(
        hass, mock_config_entry, coordinator, description_temperature
    )
    msg = ReceiveMessage(
        "TEST-TOPIC",
        json.dumps(ttn_uplink),
        0,
        False,
        "+",
        datetime.datetime.fromtimestamp(0),
    )
    await coordinator._message_received(msg)
    await hass.async_block_till_done()

    with patch.object(entity, "async_write_ha_state") as mock_async_write_ha_state:
        entity._handle_coordinator_update()
        assert entity._attr_native_value == coordinator.data.sensors.temperature
        assert mock_async_write_ha_state.call_count == 1

    assert caplog_debug.record_tuples == [
        (
            "homeassistant.components.browan.sensor",
            logging.DEBUG,
            "Manually updated LorawanSensorCoordinator.TEST-ENTRY-TITLE data",
        ),
    ]


async def test_device_info(
    hass: HomeAssistant,
    mock_config_entry: config_entries.ConfigEntry,
    description_temperature: BrowanSensorEntityDescription,
    caplog_debug: pytest.LogCaptureFixture,
) -> None:
    """Test LoRaWAN sensor device info."""
    coordinator = LorawanSensorCoordinator(
        hass, mock_config_entry, HassTBMS100.parse_uplink
    )
    entity = LorawanSensorEntity(
        hass, mock_config_entry, coordinator, description_temperature
    )

    assert entity.device_info == {
        "identifiers": {("browan", "0011223344556677")},
        "manufacturer": "browan",
        "model": "TBMS100",
        "name": "TEST-ENTRY-TITLE",
    }

    with pytest.raises(ValueError) as e3:
        entity._config.unique_id = None
        _ = entity.device_info
    assert str(e3.value) == "config.unique_id should not be None"

    assert caplog_debug.record_tuples == []
