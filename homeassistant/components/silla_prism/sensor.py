"""Sensor platform for the Silla Prism integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import override

from pysillaprism import PortError, PortState, PrismStatus

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utcnow

from .const import PORT
from .coordinator import PrismConfigEntry, PrismCoordinator
from .entity import PrismEntity

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PrismSensorEntityDescription(SensorEntityDescription):
    """Describes a Prism sensor."""

    value_fn: Callable[[PrismStatus], StateType]


# The Home Assistant state vocabulary differs from the protocol naming.
PORT_STATE_OPTIONS = {
    PortState.IDLE: "idle",
    PortState.WAITING: "waiting",
    PortState.CHARGING: "charging",
    PortState.PAUSE: "paused",
}


# The MQTT protocol only documents 0 as "no error". The fault codes are not
# specified, so they are reported as unknown rather than guessed, and logged so
# that this mapping can grow with the codes seen in the field.
ERROR_OPTIONS = {
    PortError.NONE: "none",
}


def _port_state(status: PrismStatus) -> str | None:
    state = status.port(PORT).state
    return PORT_STATE_OPTIONS.get(state) if state is not None else None


SENSORS: tuple[PrismSensorEntityDescription, ...] = (
    PrismSensorEntityDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=list(PORT_STATE_OPTIONS.values()),
        value_fn=_port_state,
    ),
    PrismSensorEntityDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.port(PORT).power,
    ),
    PrismSensorEntityDescription(
        key="current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        suggested_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.port(PORT).current,
    ),
    PrismSensorEntityDescription(
        key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status: status.port(PORT).voltage,
    ),
    PrismSensorEntityDescription(
        key="pilot",
        translation_key="pilot",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status: status.port(PORT).pilot,
    ),
    PrismSensorEntityDescription(
        key="session_energy",
        translation_key="session_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda status: status.port(PORT).session_energy,
    ),
    PrismSensorEntityDescription(
        key="total_energy",
        translation_key="total_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda status: status.port(PORT).total_energy,
    ),
    PrismSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status: status.temperature,
    ),
    PrismSensorEntityDescription(
        key="grid_power",
        translation_key="grid_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.energy.power_grid,
    ),
)

ERROR = PrismSensorEntityDescription(
    key="error",
    translation_key="error",
    device_class=SensorDeviceClass.ENUM,
    options=list(ERROR_OPTIONS.values()),
    entity_category=EntityCategory.DIAGNOSTIC,
    value_fn=lambda status: status.port(PORT).error,
)

SESSION_START = PrismSensorEntityDescription(
    key="session_start",
    translation_key="session_start",
    device_class=SensorDeviceClass.TIMESTAMP,
    entity_category=EntityCategory.DIAGNOSTIC,
    value_fn=lambda status: status.port(PORT).session_time,
)

# Prism reports the elapsed session time once a minute, and its counter runs
# about a second off the Home Assistant clock, so the derived start time jitters
# between messages. Deviations below this threshold keep the previous value.
SESSION_START_DEVIATION = timedelta(seconds=5)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PrismConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Prism sensors."""
    coordinator = entry.runtime_data
    entities: list[PrismSensor] = [
        PrismSensor(coordinator, description) for description in SENSORS
    ]
    entities.append(PrismErrorSensor(coordinator, ERROR))
    entities.append(PrismSessionStartSensor(coordinator, SESSION_START))
    async_add_entities(entities)


class PrismSensor(PrismEntity, SensorEntity):
    """A Prism sensor backed by an accumulated status field."""

    entity_description: PrismSensorEntityDescription

    def __init__(
        self,
        coordinator: PrismCoordinator,
        description: PrismSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the current value from the accumulated status."""
        return self.entity_description.value_fn(self.coordinator.device.status)


class PrismErrorSensor(PrismSensor):
    """Reports the port error code.

    Codes missing from the enum read as unknown and are logged once each, so
    that undocumented fault codes can be reported and mapped.
    """

    def __init__(
        self,
        coordinator: PrismCoordinator,
        description: PrismSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description)
        self._logged_codes: set[int] = set()

    @property
    @override
    def native_value(self) -> str | None:
        """Return the mapped error code."""
        code = self.coordinator.device.status.port(PORT).error
        if code is None:
            return None

        try:
            state = ERROR_OPTIONS[PortError(code)]
        except KeyError, ValueError:
            if code not in self._logged_codes:
                self._logged_codes.add(code)
                _LOGGER.warning(
                    "Unknown error code: %s, please report at https://github.com/home-assistant/core/issues",
                    code,
                )
            return None
        return state


class PrismSessionStartSensor(PrismSensor):
    """Reports when the running charging session started.

    Prism only publishes the elapsed session time, which is stale as soon as it
    is received. Reporting the derived start time instead keeps the value
    accurate between messages.
    """

    def __init__(
        self,
        coordinator: PrismCoordinator,
        description: PrismSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description)
        self._session_start: datetime | None = None

    @property
    @override
    def native_value(self) -> datetime | None:
        """Return the start time derived from the elapsed session time."""
        elapsed = self.entity_description.value_fn(self.coordinator.device.status)
        # Prism reports zero while no vehicle is connected.
        if not elapsed:
            self._session_start = None
            return None

        start = utcnow() - timedelta(seconds=float(elapsed))
        if (
            self._session_start is None
            or abs(start - self._session_start) > SESSION_START_DEVIATION
        ):
            self._session_start = start

        return self._session_start
