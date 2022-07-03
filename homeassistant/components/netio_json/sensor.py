"""Platform for sensor integration."""
from __future__ import annotations

import datetime
import logging

from homeassistant.components.sensor import (  # SensorStateClass,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEGREE,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    FREQUENCY_HERTZ,
    PERCENTAGE,
    POWER_WATT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NetioDeviceEntity
from .const import (  # API_GLOBAL_REVERSE_ENERGY,; API_OUTLET_REVERSE_ENERGY,
    API_GLOBAL_CURRENT,
    API_GLOBAL_ENERGY,
    API_GLOBAL_FREQUENCY,
    API_GLOBAL_LOAD,
    API_GLOBAL_MEASURE,
    API_GLOBAL_PHASE,
    API_GLOBAL_POWERFACTOR,
    API_GLOBAL_VOLTAGE,
    API_OUTLET,
    API_OUTLET_CURRENT,
    API_OUTLET_ENERGY,
    API_OUTLET_LOAD,
    API_OUTLET_PHASE,
    API_OUTLET_POWERFACTOR,
    DATA_NETIO_CLIENT,
    DOMAIN,
)
from .pdu import NetioPDUCoordinator

# from homeassistant.helpers.update_coordinator import CoordinatorEntity


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NetIO PDU Sensors from Config Entry."""
    _LOGGER.info("Async setup entry in sensor")
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_NETIO_CLIENT]

    # Fetch initial data so we have data when entities subscribe
    #
    # If the refresh fails, async_config_entry_first_refresh will
    # raise ConfigEntryNotReady and setup will try again later
    #
    # If you do not want to retry setup on failure, use
    # coordinator.async_refresh() instead
    await coordinator.async_config_entry_first_refresh()

    # try:
    #     # version = await pdu.version()
    #     await pdu.ready()
    # except Exception as exception:
    #     raise PlatformNotReady from exception
    if not coordinator.pdu.ready():
        raise PlatformNotReady

    sensors = [
        NetioVoltageSensor(coordinator, config_entry),
        NetioCurrentSensor(coordinator, config_entry),
        NetioFrequencySensor(coordinator, config_entry),
        NetioEnergySensor(coordinator, config_entry),
        NetioLoadSensor(coordinator, config_entry),
        NetioPowerfactorSensor(coordinator, config_entry),
        NetioPhaseSensor(coordinator, config_entry),
    ]

    for output in range(coordinator.pdu.output_count()):
        sensors.append(NetioOutletCurrentSensor(coordinator, config_entry, output + 1))
        sensors.append(NetioOutletEnergySensor(coordinator, config_entry, output + 1))
        sensors.append(NetioOutletLoadSensor(coordinator, config_entry, output + 1))
        sensors.append(
            NetioOutletPowerfactorSensor(coordinator, config_entry, output + 1)
        )
        # sensors.append(NetioOutletPhaseSensor(coordinator, config_entry, output + 1))

    async_add_entities(sensors, True)


class NetioSensor(NetioDeviceEntity, SensorEntity):
    """Representation of a NetIO Sensor."""

    def __init__(
        self,
        coordinator: NetioPDUCoordinator,
        config_entry: ConfigEntry,
        name: str,
        icon: str,
        measurement: str,
        unit_of_measurement: str,
        enabled_default: bool = True,
    ) -> None:
        """Initialize NetIO PDU sensor."""
        self._state: int | str | float | None = None
        self._unit_of_measurement = unit_of_measurement
        self.measurement = measurement
        self._key: str

        super().__init__(coordinator, config_entry, name, icon, enabled_default)

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return "_".join(
            [
                DOMAIN,
                self.pdu.get_device_serial_number(),
                "sensor",
                self.measurement,
            ]
        )

    @property
    def native_value(self) -> int | str | float | None:
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._state = self.coordinator.data[API_GLOBAL_MEASURE][self._key]
        self.async_write_ha_state()


class NetioOutletSensor(NetioSensor):
    """Define a NetIO PDU Outlet sensor."""

    def __init__(
        self,
        coordinator: NetioPDUCoordinator,
        config_entry: ConfigEntry,
        outlet: int,
        name: str,
        icon: str,
        measurement: str,
        unit_of_measurement: str,
        enabled_default: bool = True,
    ) -> None:
        """Initialize NetIO PDU sensor."""
        super().__init__(
            coordinator,
            config_entry,
            name,
            icon,
            measurement,
            unit_of_measurement,
        )
        self._outlet = outlet

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return "_".join(
            [
                DOMAIN,
                self.pdu.host,
                "outlet",
                str(self._outlet),
                "sensor",
                self.measurement,
            ]
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._state = self.coordinator.data[API_OUTLET][self._outlet][self._key]
        self.async_write_ha_state()


class NetioVoltageSensor(NetioSensor):
    """Defines a NetIO PDU Voltage Sensor."""

    def __init__(
        self, coordinator: NetioPDUCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize NetIO PDU sensor."""
        self._key = API_GLOBAL_VOLTAGE
        super().__init__(
            coordinator,
            config_entry,
            f"{coordinator.pdu.device_name} {SensorDeviceClass.VOLTAGE}",
            "mdi:sine-wave",
            SensorDeviceClass.VOLTAGE,
            ELECTRIC_POTENTIAL_VOLT,
        )


class NetioCurrentSensor(NetioSensor):
    """Defines a NetIO PDU Current Sensor."""

    def __init__(
        self, coordinator: NetioPDUCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize NetIO PDU sensor."""
        self._key = API_GLOBAL_CURRENT
        super().__init__(
            coordinator,
            config_entry,
            f"{coordinator.pdu.device_name} {SensorDeviceClass.CURRENT}",
            "mdi:current-ac",
            SensorDeviceClass.CURRENT,
            ELECTRIC_CURRENT_AMPERE,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._state = self.coordinator.data[API_GLOBAL_MEASURE][self._key] / 1000
        self.async_write_ha_state()


class NetioOutletCurrentSensor(NetioOutletSensor):
    """Defines a NetIO PDU Outlet Current Sensor."""

    def __init__(
        self, coordinator: NetioPDUCoordinator, config_entry: ConfigEntry, outlet: int
    ) -> None:
        """Initialize NetIO PDU sensor."""
        self._key = API_OUTLET_CURRENT
        super().__init__(
            coordinator,
            config_entry,
            outlet,
            f"{coordinator.pdu.device_name} Outlet {outlet} Current",
            "mdi:current-ac",
            SensorDeviceClass.CURRENT,
            ELECTRIC_CURRENT_AMPERE,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._state = self.coordinator.data[API_OUTLET][self._outlet][self._key] / 1000
        self.async_write_ha_state()


class NetioFrequencySensor(NetioSensor):
    """Defines a NetIO PDU Frequency Sensor."""

    def __init__(
        self, coordinator: NetioPDUCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize NetIO PDU sensor."""
        self._key = API_GLOBAL_FREQUENCY
        super().__init__(
            coordinator,
            config_entry,
            f"{coordinator.pdu.device_name} {SensorDeviceClass.FREQUENCY}",
            "mdi:sine-wave",
            SensorDeviceClass.FREQUENCY,
            FREQUENCY_HERTZ,
        )


class NetioEnergySensor(NetioSensor):
    """Defines a NetIO PDU Energy Sensor."""

    def __init__(
        self, coordinator: NetioPDUCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize NetIO PDU sensor."""
        self._key = API_GLOBAL_ENERGY
        super().__init__(
            coordinator,
            config_entry,
            f"{coordinator.pdu.device_name} {SensorDeviceClass.ENERGY}",
            "mdi:gauge",
            SensorDeviceClass.ENERGY,
            ENERGY_KILO_WATT_HOUR,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._state = self.coordinator.data[API_GLOBAL_MEASURE][self._key] / 1000
        self.async_write_ha_state()

    @property
    def device_class(self) -> str | None:
        """Return the Device Class."""
        return SensorDeviceClass.ENERGY

    @property
    def state_class(self) -> str | None:
        """Return the state class."""
        return SensorStateClass.TOTAL

    @property
    def last_reset(self) -> datetime.datetime | None:
        """Return the moment the PDU measurements were last reset."""
        return self.pdu.energy_start


class NetioOutletEnergySensor(NetioOutletSensor):
    """Defines a NetIO PDU Energy Sensor."""

    def __init__(
        self, coordinator: NetioPDUCoordinator, config_entry: ConfigEntry, outlet: int
    ) -> None:
        """Initialize NetIO PDU sensor."""
        self._key = API_OUTLET_ENERGY
        super().__init__(
            coordinator,
            config_entry,
            outlet,
            f"{coordinator.pdu.device_name} Outlet {outlet} {SensorDeviceClass.ENERGY}",
            "mdi:gauge",
            SensorDeviceClass.ENERGY,
            ENERGY_KILO_WATT_HOUR,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._state = self.coordinator.data[API_OUTLET][self._outlet][self._key] / 1000
        self.async_write_ha_state()

    @property
    def device_class(self) -> str | None:
        """Return the device_class."""
        return SensorDeviceClass.ENERGY

    @property
    def state_class(self) -> str | None:
        """Return the state_class."""
        return SensorStateClass.TOTAL

    @property
    def last_reset(self) -> datetime.datetime | None:
        """Return the moment the PDU measurements were last reset."""
        return self.pdu.energy_start


class NetioLoadSensor(NetioSensor):
    """Defines a NetIO PDU Load Sensor."""

    def __init__(
        self, coordinator: NetioPDUCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize NetIO PDU sensor."""
        self._key = API_GLOBAL_LOAD
        super().__init__(
            coordinator,
            config_entry,
            f"{coordinator.pdu.device_name} {SensorDeviceClass.POWER}",
            "mdi:flash",
            SensorDeviceClass.POWER,
            POWER_WATT,
        )


class NetioOutletLoadSensor(NetioOutletSensor):
    """Defines a NetIO PDU Outlet Load Sensor."""

    def __init__(
        self, coordinator: NetioPDUCoordinator, config_entry: ConfigEntry, outlet: int
    ) -> None:
        """Initialize NetIO PDU sensor."""
        self._key = API_OUTLET_LOAD
        super().__init__(
            coordinator,
            config_entry,
            outlet,
            f"{coordinator.pdu.device_name} Outlet {outlet} {SensorDeviceClass.POWER}",
            "mdi:flash",
            SensorDeviceClass.POWER,
            POWER_WATT,
        )


class NetioPowerfactorSensor(NetioSensor):
    """Defines a NetIO PDU Power Factor Sensor."""

    def __init__(
        self, coordinator: NetioPDUCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize NetIO PDU sensor."""
        self._key = API_GLOBAL_POWERFACTOR
        super().__init__(
            coordinator,
            config_entry,
            f"{coordinator.pdu.device_name} {SensorDeviceClass.POWER_FACTOR}",
            "mdi:information-outline",
            SensorDeviceClass.POWER_FACTOR,
            PERCENTAGE,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        powerfactor = self.coordinator.data[API_GLOBAL_MEASURE][self._key] * 100
        if powerfactor >= 999:
            _LOGGER.debug("Power Factor unavailable")
            self._state = None
            self._available = False
        else:
            self._state = powerfactor
            self._available = True
        self.async_write_ha_state()


class NetioOutletPowerfactorSensor(NetioOutletSensor):
    """Defines a NetIO PDU Power Factor Sensor."""

    def __init__(
        self, coordinator: NetioPDUCoordinator, config_entry: ConfigEntry, outlet: int
    ) -> None:
        """Initialize NetIO PDU sensor."""
        self._key = API_OUTLET_POWERFACTOR
        super().__init__(
            coordinator,
            config_entry,
            outlet,
            f"{coordinator.pdu.device_name} Outlet {outlet} {SensorDeviceClass.POWER_FACTOR}",
            "mdi:information-outline",
            SensorDeviceClass.POWER_FACTOR,
            PERCENTAGE,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        powerfactor = self.coordinator.data[API_OUTLET][self._outlet][self._key] * 100
        if powerfactor >= 999:
            _LOGGER.warning("Power Factor unavailable")
            self._state = None
            self._available = False
        else:
            self._state = powerfactor
            self._available = True
        self.async_write_ha_state()


class NetioPhaseSensor(NetioSensor):
    """Defines a NetIO PDU Phase Sensor."""

    def __init__(
        self, coordinator: NetioPDUCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize NetIO PDU sensor."""
        self._key = API_GLOBAL_PHASE
        super().__init__(
            coordinator,
            config_entry,
            f"{coordinator.pdu.device_name} Phase",
            "mdi:information-outline",
            "phase",
            DEGREE,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        phase = self.coordinator.data[API_GLOBAL_MEASURE][self._key]
        if phase >= 361:
            _LOGGER.debug("Phase unavailable")
            self._state = None
            self._available = False
        else:
            self._state = phase
            self._available = True
        self.async_write_ha_state()


class NetioOutletPhaseSensor(NetioOutletSensor):
    """Defines a NetIO PDU Phase Sensor."""

    def __init__(
        self, coordinator: NetioPDUCoordinator, config_entry: ConfigEntry, outlet: int
    ) -> None:
        """Initialize NetIO PDU sensor."""
        self._key = API_OUTLET_PHASE
        super().__init__(
            coordinator,
            config_entry,
            outlet,
            f"{coordinator.pdu.device_name} Phase",
            "mdi:information-outline",
            "phase",
            DEGREE,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        phase = self.coordinator.data[API_OUTLET][self._outlet][self._key]
        if phase >= 361:
            _LOGGER.debug("Phase unavailable")
            self._state = None
            self._available = False
        else:
            self._state = phase
            self._available = True
        self.async_write_ha_state()
