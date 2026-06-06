"""Read status of growatt inverters."""
# pylint: disable=home-assistant-missing-parallel-updates

from datetime import date, datetime
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..const import DOMAIN
from ..coordinator import GrowattConfigEntry, GrowattCoordinator
from .inverter import INVERTER_SENSOR_TYPES
from .mix import MIX_SENSOR_TYPES
from .sensor_entity_description import GrowattSensorEntityDescription
from .sph import SPH_SENSOR_TYPES
from .storage import STORAGE_SENSOR_TYPES
from .tlx import TLX_SENSOR_TYPES
from .total import TOTAL_SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)


def _create_sensors_for_device(
    coordinator: GrowattCoordinator,
) -> list[GrowattSensor]:
    """Create sensor entities for a device coordinator."""
    if coordinator.device_type == "inverter":
        sensor_descriptions = INVERTER_SENSOR_TYPES
    elif coordinator.device_type in ("tlx", "min"):
        sensor_descriptions = TLX_SENSOR_TYPES
    elif coordinator.device_type == "storage":
        sensor_descriptions = STORAGE_SENSOR_TYPES
    elif coordinator.device_type == "mix":
        sensor_descriptions = MIX_SENSOR_TYPES
    elif coordinator.device_type == "sph":
        sensor_descriptions = SPH_SENSOR_TYPES
    else:
        _LOGGER.debug(
            "Device type %s was found but is not supported right now",
            coordinator.device_type,
        )
        return []
    device_sn = coordinator.device_id
    return [
        GrowattSensor(
            coordinator,
            name=device_sn,
            serial_id=device_sn,
            unique_id=f"{device_sn}-{description.key}",
            description=description,
        )
        for description in sensor_descriptions
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: GrowattConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Growatt sensor."""
    data = config_entry.runtime_data
    entities: list[GrowattSensor] = []

    # Add total sensors
    total_coordinator = data.total_coordinator
    entities.extend(
        GrowattSensor(
            total_coordinator,
            name=f"{config_entry.data['name']} Total",
            serial_id=config_entry.data["plant_id"],
            unique_id=f"{config_entry.data['plant_id']}-{description.key}",
            description=description,
        )
        for description in TOTAL_SENSOR_TYPES
    )

    # Add sensors for each existing device
    for device_coordinator in data.devices.values():
        entities.extend(_create_sensors_for_device(device_coordinator))

    async_add_entities(entities)

    @callback
    def _async_new_device(coordinators: list[GrowattCoordinator]) -> None:
        """Add sensor entities for new devices."""
        new_entities: list[GrowattSensor] = []
        for coordinator in coordinators:
            new_entities.extend(_create_sensors_for_device(coordinator))
        if new_entities:
            async_add_entities(new_entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_new_device_{config_entry.entry_id}",
            _async_new_device,
        )
    )


class GrowattSensor(CoordinatorEntity[GrowattCoordinator], SensorEntity):
    """Representation of a Growatt Sensor."""

    _attr_has_entity_name = True
    entity_description: GrowattSensorEntityDescription

    def __init__(
        self,
        coordinator: GrowattCoordinator,
        name: str,
        serial_id: str,
        unique_id: str,
        description: GrowattSensorEntityDescription,
    ) -> None:
        """Initialize a PVOutput sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_unique_id = unique_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_id)},
            manufacturer="Growatt",
            name=name,
            serial_number=serial_id,
        )

    @property
    def native_value(self) -> StateType | date | datetime:
        """Return the state of the sensor."""
        return self.coordinator.get_data(self.entity_description)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor, if any."""
        if self.entity_description.currency:
            return self.coordinator.get_currency()
        return super().native_unit_of_measurement
