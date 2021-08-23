"""Support for OVO Energy sensors."""
from __future__ import annotations

from datetime import timedelta

from ovoenergy import OVODailyUsage
from ovoenergy.ovoenergy import OVOEnergy

from homeassistant.components.sensor import STATE_CLASS_TOTAL_INCREASING, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_CLASS_ENERGY, DEVICE_CLASS_MONETARY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import OVOEnergyDeviceEntity
from .const import DATA_CLIENT, DATA_COORDINATOR, DOMAIN

SCAN_INTERVAL = timedelta(seconds=300)
PARALLEL_UPDATES = 4


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up OVO Energy sensor based on a config entry."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    client: OVOEnergy = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]

    entities = []

    if coordinator.data:
        if coordinator.data.electricity:
            entities.append(OVOEnergyLastElectricityReading(coordinator, client))
            entities.append(
                OVOEnergyLastElectricityCost(
                    coordinator,
                    client,
                    coordinator.data.electricity[
                        len(coordinator.data.electricity) - 1
                    ].cost.currency_unit,
                )
            )
        if coordinator.data.gas:
            entities.append(OVOEnergyLastGasReading(coordinator, client))
            entities.append(
                OVOEnergyLastGasCost(
                    coordinator,
                    client,
                    coordinator.data.gas[
                        len(coordinator.data.gas) - 1
                    ].cost.currency_unit,
                )
            )

    async_add_entities(entities, True)


class OVOEnergySensor(OVOEnergyDeviceEntity, SensorEntity):
    """Defines a OVO Energy sensor."""

    _attr_state_class = STATE_CLASS_TOTAL_INCREASING

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
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
        if usage is None or not usage.gas:
            return None
        return {
            "start_time": usage.gas[-1].interval.start,
            "end_time": usage.gas[-1].interval.end,
        }
