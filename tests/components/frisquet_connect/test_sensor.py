from datetime import datetime
from decimal import Decimal
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.sensor import SensorDeviceClass

from homeassistant.helpers.entity_platform import AddEntitiesCallback
from frisquet_connect.devices.frisquet_connect_coordinator import (
    FrisquetConnectCoordinator,
)
from frisquet_connect.entities.sensor.alarm import AlarmEntity
from frisquet_connect.entities.sensor.boiler_datetime import BoilerDateTime
from frisquet_connect.entities.sensor.core_consumption import CoreConsumption
from frisquet_connect.entities.sensor.core_thermometer import CoreThermometer
from frisquet_connect.entities.sensor.heating_consumption import (
    HeatingConsumptionEntity,
)
from frisquet_connect.entities.sensor.inside_thermometer import InsideThermometerEntity
from frisquet_connect.entities.sensor.last_update import LastUpdateEntity
from frisquet_connect.entities.sensor.outside_thermometer import (
    OutsideThermometerEntity,
)
from frisquet_connect.entities.sensor.sanitary_consumption import (
    SanitaryConsumptionEntity,
)
from frisquet_connect.sensor import async_setup_entry
from frisquet_connect.const import (
    DOMAIN,
    SENSOR_HEATING_CONSUMPTION_TRANSLATIONS_KEY,
    SENSOR_SANITARY_CONSUMPTION_TRANSLATIONS_KEY,
    AlarmType,
    ConsumptionType,
)
from frisquet_connect.devices.frisquet_connect_device import (
    FrisquetConnectDevice,
)
from tests.conftest import async_core_setup_entry_with_site_id_mutated
from utils import mock_endpoints, unstub_all


@pytest.mark.asyncio
async def test_async_setup_entry_success(
    mock_hass: HomeAssistant,
    mock_entry: ConfigEntry,
    mock_add_entities: AddEntitiesCallback,
):
    # Initialize the mocks
    mock_endpoints()

    # Test the feature
    service = FrisquetConnectDevice(
        mock_entry.data.get("email"), mock_entry.data.get("password")
    )
    coordinator = FrisquetConnectCoordinator(
        mock_hass, service, mock_entry.data.get("site_id")
    )
    await coordinator._async_refresh()
    mock_hass.data[DOMAIN] = {mock_entry.unique_id: coordinator}

    await async_setup_entry(mock_hass, mock_entry, mock_add_entities)

    mock_add_entities.assert_called_once()
    entities = mock_add_entities.call_args[0][0]
    assert len(entities) == 7

    # Assertions
    for entity in entities:
        if not isinstance(
            entity,
            (
                CoreConsumption,
                CoreThermometer,
                AlarmEntity,
                LastUpdateEntity,
                BoilerDateTime,
            ),
        ):
            assert False, f"Unknown entity type: {entity.__class__.__name__}"

        entity.update()

        if isinstance(entity, SanitaryConsumptionEntity):
            entity: CoreConsumption
            assert (
                entity.translation_key == SENSOR_SANITARY_CONSUMPTION_TRANSLATIONS_KEY
            )
            assert entity._consumption_type == ConsumptionType.SANITARY
            assert entity.native_value == 196

        elif isinstance(entity, HeatingConsumptionEntity):
            entity: CoreConsumption
            assert entity.translation_key == SENSOR_HEATING_CONSUMPTION_TRANSLATIONS_KEY
            assert entity._consumption_type == ConsumptionType.HEATING
            assert entity.native_value == 1387

        elif isinstance(entity, InsideThermometerEntity):
            entity: CoreThermometer
            assert entity.native_value == Decimal(17.0)

        elif isinstance(entity, OutsideThermometerEntity):
            entity: CoreThermometer
            assert entity.native_value == Decimal(3.4)

        elif isinstance(entity, AlarmEntity):
            entity: AlarmEntity
            assert entity.device_class == SensorDeviceClass.ENUM
            assert entity.native_value == AlarmType.DISCONNECTED

        elif isinstance(entity, LastUpdateEntity):
            entity: LastUpdateEntity
            assert entity.native_value == datetime(2025, 1, 31, 10, 0, 41)

        elif isinstance(entity, BoilerDateTime):
            entity: BoilerDateTime
            assert entity.native_value == datetime(2025, 1, 31, 10, 3, 40)

        else:
            assert False, f"Unknown entity type: {entity.__class__.__name__}"

    unstub_all()


@pytest.mark.asyncio
async def test_async_setup_entry_no_site_id(
    mock_hass: HomeAssistant,
    mock_entry: ConfigEntry,
    mock_add_entities: AddEntitiesCallback,
):
    await async_core_setup_entry_with_site_id_mutated(
        async_setup_entry, mock_add_entities, mock_hass, mock_entry
    )

    unstub_all()
