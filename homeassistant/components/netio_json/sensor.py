"""Platform for sensor integration."""
from __future__ import annotations

import datetime
import logging
from typing import cast

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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NetioDeviceEntity
from .const import DATA_NETIO_CLIENT, DOMAIN
from .pdu import NetioPDU

# from homeassistant.exceptions import PlatformNotReady


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NetIO PDU Sensors from Config Entry."""
    _LOGGER.info("Async setup entry in sensor")
    pdu = hass.data[DOMAIN][config_entry.entry_id][DATA_NETIO_CLIENT]

    # try:
    #     # version = await pdu.version()
    #     await pdu.info()
    # except Exception as exception:
    #     raise PlatformNotReady from exception

    sensors = [
        NetioVoltageSensor(pdu, config_entry),
        NetioCurrentSensor(pdu, config_entry),
        NetioFrequencySensor(pdu, config_entry),
        NetioEnergySensor(pdu, config_entry),
        NetioLoadSensor(pdu, config_entry),
        NetioPowerfactorSensor(pdu, config_entry),
        NetioPhaseSensor(pdu, config_entry),
    ]

    # for output in range(pdu.output_count()):
    #     sensors.append(NetioOutletCurrentSensor(pdu, config_entry, output + 1))
    #     sensors.append(NetioOutletEnergySensor(pdu, config_entry, output + 1))
    #     sensors.append(NetioOutletLoadSensor(pdu, config_entry, output + 1))
    #     sensors.append(NetioOutletPowerfactorSensor(pdu, config_entry, output + 1))
    #     sensors.append(NetioOutletPhaseSensor(pdu, config_entry, output + 1))

    async_add_entities(sensors, True)


class NetioSensor(NetioDeviceEntity, SensorEntity):
    """Representation of a NetIO Sensor."""

    def __init__(
        self,
        pdu: NetioPDU,
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

        super().__init__(pdu, config_entry, name, icon, enabled_default)

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return "_".join(
            [
                DOMAIN,
                self.pdu.host,
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


class NetioOutletSensor(NetioSensor):
    """Define a NetIO PDU Outlet Voltage sensor."""

    def __init__(
        self,
        pdu: NetioPDU,
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
            pdu,
            config_entry,
            name,
            icon,
            measurement,
            unit_of_measurement,
        )
        self.outlet = outlet

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return "_".join(
            [
                DOMAIN,
                self.pdu.host,
                "outlet",
                str(self.outlet),
                "sensor",
                self.measurement,
            ]
        )


class NetioVoltageSensor(NetioSensor):
    """Defines a NetIO PDU Voltage Sensor."""

    def __init__(self, pdu: NetioPDU, config_entry: ConfigEntry) -> None:
        """Initialize NetIO PDU sensor."""
        super().__init__(
            pdu,
            config_entry,
            f"{pdu.device_name} Voltage",
            "mdi:sine-wave",
            SensorDeviceClass.VOLTAGE,
            ELECTRIC_POTENTIAL_VOLT,
        )

    async def _pdu_update(self) -> None:
        """Update NetIO PDU entity."""
        self._state = cast(float, await self.pdu.get_global_measures("Voltage"))


class NetioCurrentSensor(NetioSensor):
    """Defines a NetIO PDU Current Sensor."""

    def __init__(self, pdu: NetioPDU, config_entry: ConfigEntry) -> None:
        """Initialize NetIO PDU sensor."""
        super().__init__(
            pdu,
            config_entry,
            f"{pdu.device_name} Current",
            "mdi:current-ac",
            SensorDeviceClass.CURRENT,
            ELECTRIC_CURRENT_AMPERE,
        )

    async def _pdu_update(self) -> None:
        """Update NetIO PDU entity."""
        self._state = (
            cast(int, await self.pdu.get_global_measures("TotalCurrent")) / 1000
        )


class NetioOutletCurrentSensor(NetioOutletSensor):
    """Defines a NetIO PDU Outlet Current Sensor."""

    def __init__(self, pdu: NetioPDU, config_entry: ConfigEntry, outlet: int) -> None:
        """Initialize NetIO PDU sensor."""
        super().__init__(
            pdu,
            config_entry,
            outlet,
            f"{pdu.device_name} Outlet {outlet} Current",
            "mdi:current-ac",
            SensorDeviceClass.CURRENT,
            ELECTRIC_CURRENT_AMPERE,
        )

    async def _pdu_update(self) -> None:
        """Update NetIO PDU entity."""
        self._state = (
            cast(int, await self.pdu.get_outlet(self.outlet, "Current")) / 1000
        )


class NetioFrequencySensor(NetioSensor):
    """Defines a NetIO PDU Frequency Sensor."""

    def __init__(self, pdu: NetioPDU, config_entry: ConfigEntry) -> None:
        """Initialize NetIO PDU sensor."""
        super().__init__(
            pdu,
            config_entry,
            f"{pdu.device_name} Frequency",
            "mdi:sine-wave",
            SensorDeviceClass.FREQUENCY,
            FREQUENCY_HERTZ,
        )

    async def _pdu_update(self) -> None:
        """Update NetIO PDU entity."""
        self._state = cast(float, await self.pdu.get_global_measures("Frequency"))


class NetioEnergySensor(NetioSensor):
    """Defines a NetIO PDU Energy Sensor."""

    def __init__(self, pdu: NetioPDU, config_entry: ConfigEntry) -> None:
        """Initialize NetIO PDU sensor."""
        super().__init__(
            pdu,
            config_entry,
            f"{pdu.device_name} Energy",
            "mdi:gauge",
            SensorDeviceClass.ENERGY,
            ENERGY_KILO_WATT_HOUR,
        )

    async def _pdu_update(self) -> None:
        """Update NetIO PDU entity."""
        self._state = (
            cast(int, await self.pdu.get_global_measures("TotalEnergy")) / 1000
        )

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

    def __init__(self, pdu: NetioPDU, config_entry: ConfigEntry, outlet: int) -> None:
        """Initialize NetIO PDU sensor."""
        super().__init__(
            pdu,
            config_entry,
            outlet,
            f"{pdu.device_name} Outlet {outlet} Energy",
            "mdi:gauge",
            SensorDeviceClass.ENERGY,
            ENERGY_KILO_WATT_HOUR,
        )

    async def _pdu_update(self) -> None:
        """Update NetIO PDU entity."""
        self._state = cast(int, await self.pdu.get_outlet(self.outlet, "Energy")) / 1000

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

    def __init__(self, pdu: NetioPDU, config_entry: ConfigEntry) -> None:
        """Initialize NetIO PDU sensor."""
        super().__init__(
            pdu,
            config_entry,
            f"{pdu.device_name} Load",
            "mdi:flash",
            SensorDeviceClass.POWER,
            POWER_WATT,
        )

    async def _pdu_update(self) -> None:
        """Update NetIO PDU entity."""
        self._state = cast(int, await self.pdu.get_global_measures("TotalLoad"))


class NetioOutletLoadSensor(NetioOutletSensor):
    """Defines a NetIO PDU Outlet Load Sensor."""

    def __init__(self, pdu: NetioPDU, config_entry: ConfigEntry, outlet: int) -> None:
        """Initialize NetIO PDU sensor."""
        super().__init__(
            pdu,
            config_entry,
            outlet,
            f"{pdu.device_name} Outlet {outlet} Load",
            "mdi:flash",
            SensorDeviceClass.POWER,
            POWER_WATT,
        )

    async def _pdu_update(self) -> None:
        """Update NetIO PDU entity."""
        self._state = cast(int, await self.pdu.get_outlet(self.outlet, "Load"))


class NetioPowerfactorSensor(NetioSensor):
    """Defines a NetIO PDU Power Factor Sensor."""

    def __init__(self, pdu: NetioPDU, config_entry: ConfigEntry) -> None:
        """Initialize NetIO PDU sensor."""
        super().__init__(
            pdu,
            config_entry,
            f"{pdu.device_name} Power Factor",
            "mdi:information-outline",
            SensorDeviceClass.POWER_FACTOR,
            PERCENTAGE,
        )

    async def _pdu_update(self) -> None:
        """Update NetIO PDU entity."""
        powerfactor = cast(
            float, await self.pdu.get_global_measures("TotalPowerFactor")
        )
        if powerfactor >= 999:
            _LOGGER.warning("Power Factor unavailable")
            self._state = None
            self._available = False
        else:
            self._state = powerfactor
            self._available = True


class NetioOutletPowerfactorSensor(NetioOutletSensor):
    """Defines a NetIO PDU Power Factor Sensor."""

    def __init__(self, pdu: NetioPDU, config_entry: ConfigEntry, outlet: int) -> None:
        """Initialize NetIO PDU sensor."""
        super().__init__(
            pdu,
            config_entry,
            outlet,
            f"{pdu.device_name} Outlet {outlet} Power Factor",
            "mdi:information-outline",
            SensorDeviceClass.POWER_FACTOR,
            PERCENTAGE,
        )

    async def _pdu_update(self) -> None:
        """Update NetIO PDU entity."""
        powerfactor = cast(float, await self.pdu.get_outlet(self.outlet, "PowerFactor"))
        if powerfactor >= 999:
            _LOGGER.warning("Power Factor unavailable")
            self._state = None
            self._available = False
        else:
            self._state = powerfactor
            self._available = True


class NetioPhaseSensor(NetioSensor):
    """Defines a NetIO PDU Phase Sensor."""

    def __init__(self, pdu: NetioPDU, config_entry: ConfigEntry) -> None:
        """Initialize NetIO PDU sensor."""
        super().__init__(
            pdu,
            config_entry,
            f"{pdu.device_name} Phase",
            "mdi:information-outline",
            "phase",
            DEGREE,
        )

    async def _pdu_update(self) -> None:
        """Update NetIO PDU entity."""
        phase = cast(float, await self.pdu.get_global_measures("TotalPhase"))
        if phase >= 361:
            _LOGGER.warning("Phase unavailable")
            self._state = None
            self._available = False
        else:
            self._state = phase
            self._available = True


class NetioOutletPhaseSensor(NetioOutletSensor):
    """Defines a NetIO PDU Phase Sensor."""

    def __init__(self, pdu: NetioPDU, config_entry: ConfigEntry, outlet: int) -> None:
        """Initialize NetIO PDU sensor."""
        super().__init__(
            pdu,
            config_entry,
            outlet,
            f"{pdu.device_name} Phase",
            "mdi:information-outline",
            "phase",
            DEGREE,
        )

    async def _pdu_update(self) -> None:
        """Update NetIO PDU entity."""
        phase = cast(float, await self.pdu.get_outlet(self.outlet, "Phase"))
        if phase >= 361:
            _LOGGER.warning("Phase unavailable")
            self._state = None
            self._available = False
        else:
            self._state = phase
            self._available = True
