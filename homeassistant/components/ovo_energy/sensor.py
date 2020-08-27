"""Support for OVO Energy sensors."""
from datetime import timedelta
import logging

from ovoenergy import OVODailyUsage
from ovoenergy.ovoenergy import OVOEnergy

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import OVOEnergyDeviceEntity
from .const import DATA_CLIENT, DATA_COORDINATOR, DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=300)
PARALLEL_UPDATES = 4


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
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

    async_add_entities(
        entities,
        True,
    )


class OVOEnergySensor(OVOEnergyDeviceEntity):
    """Defines a OVO Energy sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        client: OVOEnergy,
        key: str,
        name: str,
        icon: str,
        unit_of_measurement: str = "",
    ) -> None:
        """Initialize OVO Energy sensor."""
        self._unit_of_measurement = unit_of_measurement

        super().__init__(coordinator, client, key, name, icon)

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement


class OVOEnergyLastElectricityReading(OVOEnergySensor):
    """Defines a OVO Energy last reading sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, client: OVOEnergy):
        """Initialize OVO Energy sensor."""

        super().__init__(
            coordinator,
            client,
            f"{client.account_id}_last_electricity_reading",
            "OVO Last Electricity Reading",
            "mdi:flash",
            "kWh",
        )

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        usage: OVODailyUsage = self._coordinator.data
        if usage is None or not usage.electricity:
            return None
        return usage.electricity[-1].consumption

    @property
    def device_state_attributes(self) -> object:
        """Return the attributes of the sensor."""
        usage: OVODailyUsage = self._coordinator.data
        if usage is None or not usage.electricity:
            return None
        return {
            "start_time": usage.electricity[-1].interval.start,
            "end_time": usage.electricity[-1].interval.end,
        }


class OVOEnergyLastGasReading(OVOEnergySensor):
    """Defines a OVO Energy last reading sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, client: OVOEnergy):
        """Initialize OVO Energy sensor."""

        super().__init__(
            coordinator,
            client,
            f"{DOMAIN}_{client.account_id}_last_gas_reading",
            "OVO Last Gas Reading",
            "mdi:gas-cylinder",
            "kWh",
        )

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        usage: OVODailyUsage = self._coordinator.data
        if usage is None or not usage.gas:
            return None
        return usage.gas[-1].consumption

    @property
    def device_state_attributes(self) -> object:
        """Return the attributes of the sensor."""
        usage: OVODailyUsage = self._coordinator.data
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
    ):
        """Initialize OVO Energy sensor."""
        super().__init__(
            coordinator,
            client,
            f"{DOMAIN}_{client.account_id}_last_electricity_cost",
            "OVO Last Electricity Cost",
            "mdi:cash-multiple",
            currency,
        )

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        usage: OVODailyUsage = self._coordinator.data
        if usage is None or not usage.electricity:
            return None
        return usage.electricity[-1].cost.amount

    @property
    def device_state_attributes(self) -> object:
        """Return the attributes of the sensor."""
        usage: OVODailyUsage = self._coordinator.data
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
    ):
        """Initialize OVO Energy sensor."""
        super().__init__(
            coordinator,
            client,
            f"{DOMAIN}_{client.account_id}_last_gas_cost",
            "OVO Last Gas Cost",
            "mdi:cash-multiple",
            currency,
        )

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        usage: OVODailyUsage = self._coordinator.data
        if usage is None or not usage.gas:
            return None
        return usage.gas[-1].cost.amount

    @property
    def device_state_attributes(self) -> object:
        """Return the attributes of the sensor."""
        usage: OVODailyUsage = self._coordinator.data
        if usage is None or not usage.gas:
            return None
        return {
            "start_time": usage.gas[-1].interval.start,
            "end_time": usage.gas[-1].interval.end,
        }
