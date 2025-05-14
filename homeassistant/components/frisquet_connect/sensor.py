import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from frisquet_connect.core_setup_entity import async_initialize_entity
from frisquet_connect.entities.sensor.alarm import AlarmEntity
from frisquet_connect.entities.sensor.boiler_datetime import BoilerDateTime
from frisquet_connect.entities.sensor.core_consumption import (
    CoreConsumption,
)
from frisquet_connect.entities.sensor.core_thermometer import (
    CoreThermometer,
)
from frisquet_connect.entities.sensor.heating_consumption import (
    HeatingConsumptionEntity,
)
from frisquet_connect.entities.sensor.inside_thermometer import (
    InsideThermometerEntity,
)
from frisquet_connect.entities.sensor.last_update import LastUpdateEntity
from frisquet_connect.entities.sensor.outside_thermometer import (
    OutsideThermometerEntity,
)
from frisquet_connect.entities.sensor.sanitary_consumption import (
    SanitaryConsumptionEntity,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    (initialization_success, coordinator) = await async_initialize_entity(
        hass, entry, __name__
    )
    if not initialization_success:
        async_add_entities([], update_before_add=True)
        return

    entities: list[CoreConsumption | CoreThermometer | AlarmEntity] = [
        SanitaryConsumptionEntity(coordinator),
        HeatingConsumptionEntity(coordinator),
        OutsideThermometerEntity(coordinator),
        AlarmEntity(coordinator),
        LastUpdateEntity(coordinator),
        BoilerDateTime(coordinator),
    ]
    for zone in coordinator.data.zones:
        entity = InsideThermometerEntity(coordinator, zone.label_id)
        entities.append(entity)

    _LOGGER.debug(f"{len(entities)} entity/entities initialized")

    async_add_entities(entities, update_before_add=True)
