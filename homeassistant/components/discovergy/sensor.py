"""Discovergy sensor entity."""
from dataclasses import dataclass, field
import logging

from pydiscovergy import Discovergy
from pydiscovergy.error import AccessTokenExpired, HTTPError
from pydiscovergy.models import Meter

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
    VOLUME_CUBIC_METERS,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from . import DiscovergyData
from .const import DOMAIN, MANUFACTURER, MIN_TIME_BETWEEN_UPDATES

PARALLEL_UPDATES = 1
_LOGGER = logging.getLogger(__name__)


@dataclass
class DiscovergyMixin:
    """Mixin for alternative keys."""

    alternative_keys: list = field(default_factory=lambda: [])
    scale: int = field(default_factory=lambda: 1000)


@dataclass
class DiscovergySensorEntityDescription(DiscovergyMixin, SensorEntityDescription):
    """Define Sensor entity description class."""


GAS_SENSORS: tuple[DiscovergySensorEntityDescription, ...] = (
    DiscovergySensorEntityDescription(
        key="volume",
        name="Total consumption",
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)

ELECTRICITY_SENSORS: tuple[DiscovergySensorEntityDescription, ...] = (
    # power sensors
    DiscovergySensorEntityDescription(
        key="power",
        name="Total power",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DiscovergySensorEntityDescription(
        key="power1",
        name="Phase 1 power",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        alternative_keys=["phase1Power"],
    ),
    DiscovergySensorEntityDescription(
        key="power2",
        name="Phase 2 power",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        alternative_keys=["phase2Power"],
    ),
    DiscovergySensorEntityDescription(
        key="power3",
        name="Phase 3 power",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        alternative_keys=["phase3Power"],
    ),
    # voltage sensors
    DiscovergySensorEntityDescription(
        key="phase1Voltage",
        name="Phase 1 voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    DiscovergySensorEntityDescription(
        key="phase2Voltage",
        name="Phase 2 voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    DiscovergySensorEntityDescription(
        key="phase3Voltage",
        name="Phase 3 voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    # energy sensors
    DiscovergySensorEntityDescription(
        key="energy",
        name="Total consumption",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        scale=10000000000,
    ),
    DiscovergySensorEntityDescription(
        key="energyOut",
        name="Total production",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        scale=10000000000,
    ),
)


def get_coordinator_for_meter(
    hass: HomeAssistant, meter: Meter, discovergy_instance: Discovergy
) -> DataUpdateCoordinator:
    """Create a new DataUpdateCoordinator for given meter."""

    async def async_update_data():
        """Fetch data from API endpoint."""
        try:
            return await discovergy_instance.get_last_reading(meter.get_meter_id())
        except AccessTokenExpired as err:
            raise ConfigEntryAuthFailed(
                "Got token expired while communicating with API"
            ) from err
        except HTTPError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except Exception as err:  # pylint: disable=broad-except
            raise UpdateFailed(
                f"Unexpected error while communicating with API: {err}"
            ) from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="sensor",
        update_method=async_update_data,
        update_interval=MIN_TIME_BETWEEN_UPDATES,
    )
    return coordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Discovergy sensors."""
    data: DiscovergyData = hass.data[DOMAIN][entry.entry_id]
    discovergy_instance: Discovergy = data.api_client
    meters: list[Meter] = data.meters  # always returns a list

    entities = []
    for meter in meters:
        # Get coordinator for meter, set config entry and fetch initial data
        # so we have data when entities are added
        coordinator = get_coordinator_for_meter(hass, meter, discovergy_instance)
        coordinator.config_entry = entry
        await coordinator.async_config_entry_first_refresh()

        # add coordinator to data for diagnostics
        data.coordinators[meter.get_meter_id()] = coordinator

        sensors = None
        if meter.measurement_type == "ELECTRICITY":
            sensors = ELECTRICITY_SENSORS
        elif meter.measurement_type == "GAS":
            sensors = GAS_SENSORS

        if sensors is not None:
            for description in sensors:
                keys = [description.key] + description.alternative_keys

                # check if this meter has this data, then add this sensor
                for key in keys:
                    if key in coordinator.data.values:
                        entities.append(
                            DiscovergySensor(description, meter, coordinator)
                        )

    async_add_entities(entities, False)


class DiscovergySensor(CoordinatorEntity, SensorEntity):
    """Represents a discovergy smart meter sensor."""

    entity_description: DiscovergySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        description: DiscovergySensorEntityDescription,
        meter: Meter,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_name = (
            f"{meter.measurement_type.capitalize()} "
            f"{meter.location.street} "
            f"{meter.location.street_number} - "
            f"{description.name}"
        )
        self._attr_unique_id = f"{meter.full_serial_number}-{description.key}"
        self._attr_device_info = {
            ATTR_IDENTIFIERS: {(DOMAIN, meter.get_meter_id())},
            ATTR_NAME: f"{meter.measurement_type.capitalize()} {meter.location.street} {meter.location.street_number}",
            ATTR_MODEL: f"{meter.type} {meter.full_serial_number}",
            ATTR_MANUFACTURER: MANUFACTURER,
        }

    @property
    def native_value(self) -> StateType:
        """Return the sensor state."""
        return (
            self.coordinator.data.values[self.entity_description.key]
            / self.entity_description.scale
        )
