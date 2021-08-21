"""Support for OVO Energy sensors."""
from __future__ import annotations

from datetime import timedelta
from typing import Callable, Final

from ovoenergy import OVODailyUsage
from ovoenergy.ovoenergy import OVOEnergy

from homeassistant.components.sensor import STATE_CLASS_TOTAL_INCREASING, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_CLASS_ENERGY, DEVICE_CLASS_MONETARY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from . import OVOEnergyDeviceEntity
from .const import DATA_CLIENT, DATA_COORDINATOR, DOMAIN

SCAN_INTERVAL = timedelta(seconds=300)
PARALLEL_UPDATES = 4

KEY_LAST_ELECTRICITY_COST: Final = "last_electricity_cost"
KEY_LAST_GAS_COST: Final = "last_gas_cost"


@dataclass
class OVOEnergySensorEntityDescription(SensorEntityDescription):
    """Class describing System Bridge sensor entities."""

    value: Callable[[OVODailyUsage], StateType] = round


SENSOR_TYPES_ELECTRICITY: tuple[OVOEnergySensorEntityDescription, ...] = (
    OVOEnergySensorEntityDescription(
        key="last_electricity_reading",
        name="OVO Last Electricity Reading",
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        value=lambda usage: usage.electricity[-1].consumption,
    ),
    OVOEnergySensorEntityDescription(
        key=KEY_LAST_ELECTRICITY_COST,
        name="OVO Last Electricity Cost",
        device_class=DEVICE_CLASS_MONETARY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        icon="mdi:cash-multiple",
        value=lambda usage: usage.electricity[-1].consumption,
    ),
    OVOEnergySensorEntityDescription(
        key="last_electricity_start_time",
        name="OVO Last Electricity Start Time",
        entity_registry_enabled_default=False,
        device_class=DEVICE_CLASS_TIMESTAMP,
        value=lambda usage: dt_util.as_utc(usage.electricity[-1].interval.start),
    ),
    OVOEnergySensorEntityDescription(
        key="last_electricity_end_time",
        name="OVO Last Electricity End Time",
        entity_registry_enabled_default=False,
        device_class=DEVICE_CLASS_TIMESTAMP,
        value=lambda usage: dt_util.as_utc(usage.electricity[-1].interval.end),
    ),
)

SENSOR_TYPES_GAS: tuple[OVOEnergySensorEntityDescription, ...] = (
    OVOEnergySensorEntityDescription(
        key="last_gas_reading",
        name="OVO Last Gas Reading",
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        icon="mdi:gas-cylinder",
        value=lambda usage: usage.gas[-1].consumption,
    ),
    OVOEnergySensorEntityDescription(
        key=KEY_LAST_GAS_COST,
        name="OVO Last Gas Cost",
        device_class=DEVICE_CLASS_MONETARY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        icon="mdi:cash-multiple",
        value=lambda usage: usage.gas[-1].consumption,
    ),
    OVOEnergySensorEntityDescription(
        key="last_gas_start_time",
        name="OVO Last Gas Start Time",
        entity_registry_enabled_default=False,
        device_class=DEVICE_CLASS_TIMESTAMP,
        value=lambda usage: dt_util.as_utc(usage.gas[-1].interval.start),
    ),
    OVOEnergySensorEntityDescription(
        key="last_gas_end_time",
        name="OVO Last Gas End Time",
        entity_registry_enabled_default=False,
        device_class=DEVICE_CLASS_TIMESTAMP,
        value=lambda usage: dt_util.as_utc(usage.gas[-1].interval.end),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up OVO Energy sensor based on a config entry."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    client: OVOEnergy = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]

    entities = []

    if coordinator.data:
        if coordinator.data.electricity:
            for description in SENSOR_TYPES_ELECTRICITY:
                if description.key == KEY_LAST_ELECTRICITY_COST:
                    description.native_unit_of_measurement = (
                        coordinator.data.electricity[-1].cost.currency_unit
                    )
                entities.append(OVOEnergySensor(coordinator, description, client))
        if coordinator.data.gas:
            for description in SENSOR_TYPES_GAS:
                if description.key == KEY_LAST_GAS_COST:
                    description.native_unit_of_measurement = coordinator.data.gas[
                        -1
                    ].cost.currency_unit
                entities.append(OVOEnergySensor(coordinator, description, client))

    async_add_entities(entities, True)


class OVOEnergySensor(OVOEnergyDeviceEntity, SensorEntity):
    """Define a OVO Energy sensor."""

    coordinator: DataUpdateCoordinator
    entity_description: OVOEnergySensorEntityDescription

    _attr_state_class = STATE_CLASS_TOTAL_INCREASING

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: OVOEnergySensorEntityDescription,
        client: OVOEnergy,
        key: str,
        name: str,
        icon: str,
        device_class: str | None,
        unit_of_measurement: str | None,
    ) -> None:
        """Initialize OVO Energy sensor."""
        self._attr_device_class = device_class
        self._unit_of_measurement = unit_of_measurement

        super().__init__(coordinator, client, key, name, icon)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement


class OVOEnergyLastElectricityReading(OVOEnergySensor):
    """Defines a OVO Energy last reading sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, client: OVOEnergy) -> None:
        """Initialize OVO Energy sensor."""

        super().__init__(
            coordinator,
            client,
            f"{client.account_id}_last_electricity_reading",
            "OVO Last Electricity Reading",
            "mdi:flash",
            DEVICE_CLASS_ENERGY,
            "kWh",
        )

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        usage: OVODailyUsage = self.coordinator.data
        if usage is None or not usage.electricity:
            return None
        return usage.electricity[-1].consumption

    @property
    def extra_state_attributes(self) -> object:
        """Return the attributes of the sensor."""
        usage: OVODailyUsage = self.coordinator.data
        if usage is None or not usage.electricity:
            return None
        return {
            "start_time": usage.electricity[-1].interval.start,
            "end_time": usage.electricity[-1].interval.end,
        }


class OVOEnergyLastGasReading(OVOEnergySensor):
    """Defines a OVO Energy last reading sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, client: OVOEnergy) -> None:
        """Initialize OVO Energy sensor."""

        super().__init__(
            coordinator,
            client,
            f"{DOMAIN}_{client.account_id}_last_gas_reading",
            "OVO Last Gas Reading",
            "mdi:gas-cylinder",
            DEVICE_CLASS_ENERGY,
            "kWh",
        )
        self.entity_description = description

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        usage: OVODailyUsage = self.coordinator.data
        if usage is None or not usage.gas:
            return None
        return usage.gas[-1].consumption

    @property
    def extra_state_attributes(self) -> object:
        """Return the attributes of the sensor."""
        usage: OVODailyUsage = self.coordinator.data
        if usage is None or not usage.gas:
            return None
        return {
            "start_time": usage.gas[-1].interval.start,
            "end_time": usage.gas[-1].interval.end,
        }


class OVOEnergyLastElectricityCost(OVOEnergySensor):
    """Defines a OVO Energy last cost sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, client: OVOEnergy, currency: str
    ) -> None:
        """Initialize OVO Energy sensor."""
        super().__init__(
            coordinator,
            client,
            f"{DOMAIN}_{client.account_id}_last_electricity_cost",
            "OVO Last Electricity Cost",
            "mdi:cash-multiple",
            DEVICE_CLASS_MONETARY,
            currency,
        )

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        usage: OVODailyUsage = self.coordinator.data
        if usage is None or not usage.electricity:
            return None
        return usage.electricity[-1].cost.amount

    @property
    def extra_state_attributes(self) -> object:
        """Return the attributes of the sensor."""
        usage: OVODailyUsage = self.coordinator.data
        if usage is None or not usage.electricity:
            return None
        return {
            "start_time": usage.electricity[-1].interval.start,
            "end_time": usage.electricity[-1].interval.end,
        }


class OVOEnergyLastGasCost(OVOEnergySensor):
    """Defines a OVO Energy last cost sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, client: OVOEnergy, currency: str
    ) -> None:
        """Initialize OVO Energy sensor."""
        super().__init__(
            coordinator,
            client,
            f"{DOMAIN}_{client.account_id}_last_gas_cost",
            "OVO Last Gas Cost",
            "mdi:cash-multiple",
            DEVICE_CLASS_MONETARY,
            currency,
        )

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        usage: OVODailyUsage = self.coordinator.data
        if usage is None or not usage.gas:
            return None
        return usage.gas[-1].cost.amount

    @property
    def extra_state_attributes(self) -> object:
        """Return the attributes of the sensor."""
        usage: OVODailyUsage = self.coordinator.data
        return self.entity_description.value(usage)
