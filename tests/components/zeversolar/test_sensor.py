"""Test the sensor classes."""

from unittest.mock import patch

from zeversolar import StatusEnum, ZeverSolarClient, ZeverSolarData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.zeversolar.const import DOMAIN
from homeassistant.components.zeversolar.coordinator import ZeversolarCoordinator
from homeassistant.components.zeversolar.entity import ZeversolarEntity
from homeassistant.components.zeversolar.sensor import (
    ZeversolarEntityDescription,
    ZeversolarSensor,
    async_setup_entry,
)
from homeassistant.const import EntityCategory, UnitOfPower
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, MockModule, mock_integration


async def test_ZeversolarEntityDescription_constructor(hass: HomeAssistant) -> None:
    """Simple test for construction and initialization."""

    description = ZeversolarEntityDescription(
        key="pac",
        translation_key="pac",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda data: data.pac,
    )

    assert type(description) is ZeversolarEntityDescription
    assert issubclass(type(description), SensorEntityDescription)


def async_add_entities2(entities):
    """Add entities to a sensor as simulation for unit test. Helper method."""
    for value in entities:
        assert value.__class__ is ZeversolarSensor


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test the sensor setup."""
    mock_integration(hass, MockModule(DOMAIN))

    config = MockConfigEntry(
        data={
            "host": "my host",
            "port": 10200,
            "data": "test",
        },
        domain=DOMAIN,
        options={},
        title="My NEW_DOMAIN",
    )

    zeverData = ZeverSolarData(
        wifi_enabled=False,
        serial_or_registry_id="1223",
        registry_key="A-2",
        hardware_version="M10",
        software_version="123-23",
        reported_datetime="19900101 23:00",
        communication_status=StatusEnum.OK,
        num_inverters=1,
        serial_number="123456778",
        pac=1234,
        energy_today=123,
        status=StatusEnum.OK,
        meter_status=StatusEnum.OK,
    )

    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(
            DOMAIN,
            {
                "data": "test2",
            },
        )

    config.add_to_hass(hass)

    with patch.object(ZeverSolarClient, "get_data") as client_mock:
        coordinator = ZeversolarCoordinator(hass=hass, entry=config)
        coordinator.data = zeverData
        hass.data[DOMAIN][config.entry_id] = coordinator

        client_mock.return_value = zeverData

        await coordinator._async_update_data()
        assert coordinator.last_update_success

        await async_setup_entry(hass, config, async_add_entities2)

    # assert
    # is done in async_add_entities


async def test_ZeversolarSensor_native_value(hass: HomeAssistant) -> None:
    """Simple test for construction and initialization."""

    description = ZeversolarEntityDescription(
        key="pac",
        translation_key="pac",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda data: data.pac,
    )

    config = MockConfigEntry(
        data={
            "host": "my host",
            "port": 10200,
            "data": "test",
        },
        domain=DOMAIN,
        options={},
        title="My NEW_DOMAIN",
    )

    mock_integration(hass, MockModule(DOMAIN))

    config = MockConfigEntry(
        data={
            "host": "my host",
            "port": 10200,
            "data": "test",
        },
        domain=DOMAIN,
        options={},
        title="My NEW_DOMAIN",
    )

    zeverData = ZeverSolarData(
        wifi_enabled=False,
        serial_or_registry_id="1223",
        registry_key="A-2",
        hardware_version="M10",
        software_version="123-23",
        reported_datetime="19900101 23:00",
        communication_status=StatusEnum.OK,
        num_inverters=1,
        serial_number="123456778",
        pac=1234,
        energy_today=123,
        status=StatusEnum.OK,
        meter_status=StatusEnum.OK,
    )

    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(
            DOMAIN,
            {
                "data": "test2",
            },
        )

    config.add_to_hass(hass)

    with patch.object(ZeverSolarClient, "get_data") as client_mock:
        coordinator = ZeversolarCoordinator(hass=hass, entry=config)
        coordinator.data = zeverData
        hass.data[DOMAIN][config.entry_id] = coordinator

        client_mock.return_value = zeverData

        await coordinator._async_update_data()
        assert coordinator.last_update_success

        await async_setup_entry(hass, config, async_add_entities2)

        sensor = ZeversolarSensor(description=description, coordinator=coordinator)

        assert type(sensor) is ZeversolarSensor
        assert issubclass(type(sensor), ZeversolarEntity)
        assert issubclass(type(sensor), SensorEntity)

        result_value = sensor.native_value
        assert result_value == zeverData.pac
