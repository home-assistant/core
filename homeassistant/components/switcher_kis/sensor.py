"""Switcher integration Sensor platform."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import cast, override

from aioswitcher.device import (
    DeviceCategory,
    SwitcherBase,
    SwitcherPowerBase,
    SwitcherThermostatBase,
    SwitcherTimedBase,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    Platform,
    UnitOfElectricCurrent,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from . import SwitcherConfigEntry
from .const import SIGNAL_DEVICE_ADD
from .coordinator import SwitcherDataUpdateCoordinator
from .entity import SwitcherEntity
from .utils import deprecate_entity

PARALLEL_UPDATES = 0

# Broadcasts report whole seconds, so the computed shutdown time jitters.
SHUTDOWN_TIME_VARIANCE = timedelta(seconds=10)


def _shutdown_time(data: SwitcherBase) -> datetime | None:
    """Calculate the shutdown time from the remaining time."""
    if not (
        remaining := dt_util.parse_duration(
            cast(SwitcherTimedBase, data).remaining_time
        )
    ):
        return None
    return dt_util.utcnow() + remaining


@dataclass(frozen=True, kw_only=True)
class SwitcherSensorEntityDescription(SensorEntityDescription):
    """Class to describe a Switcher sensor entity."""

    value_fn: Callable[[SwitcherBase], StateType | datetime]
    ignored_variance: timedelta | None = None


POWER_SENSORS: list[SwitcherSensorEntityDescription] = [
    SwitcherSensorEntityDescription(
        key="power_consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: cast(SwitcherPowerBase, data).power_consumption,
    ),
    SwitcherSensorEntityDescription(
        key="electric_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: cast(SwitcherPowerBase, data).electric_current,
    ),
]
TIME_SENSORS: list[SwitcherSensorEntityDescription] = [
    SwitcherSensorEntityDescription(
        key="shutdown_time",
        translation_key="shutdown_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        ignored_variance=SHUTDOWN_TIME_VARIANCE,
        value_fn=_shutdown_time,
    ),
    SwitcherSensorEntityDescription(
        key="auto_off",
        translation_key="auto_off",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        entity_registry_enabled_default=False,
        value_fn=lambda data: (
            int(duration.total_seconds())
            if (
                duration := dt_util.parse_duration(
                    cast(SwitcherTimedBase, data).auto_shutdown
                )
            )
            is not None
            else None
        ),
    ),
]
# Replaced by the shutdown time and auto-off sensors.
DEPRECATED_TIME_SENSORS: list[SwitcherSensorEntityDescription] = [
    SwitcherSensorEntityDescription(
        key="remaining_time",
        translation_key="remaining_time",
        value_fn=lambda data: cast(SwitcherTimedBase, data).remaining_time,
    ),
    SwitcherSensorEntityDescription(
        key="auto_off_set",
        translation_key="auto_shutdown",
        entity_registry_enabled_default=False,
        value_fn=lambda data: cast(SwitcherTimedBase, data).auto_shutdown,
    ),
]
TEMPERATURE_SENSORS: list[SwitcherSensorEntityDescription] = [
    SwitcherSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: cast(SwitcherThermostatBase, data).temperature,
    ),
]

POWER_PLUG_SENSORS = POWER_SENSORS
HEATER_SENSORS = [*POWER_SENSORS, *TIME_SENSORS]
THERMOSTAT_SENSORS = TEMPERATURE_SENSORS


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SwitcherConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Switcher sensor from config entry."""
    entity_registry = er.async_get(hass)

    @callback
    def async_add_sensors(coordinator: SwitcherDataUpdateCoordinator) -> None:
        """Add sensors from Switcher device."""
        if coordinator.data.device_type.category is DeviceCategory.POWER_PLUG:
            async_add_entities(
                SwitcherSensorEntity(coordinator, description)
                for description in POWER_PLUG_SENSORS
            )
        elif coordinator.data.device_type.category in [
            DeviceCategory.WATER_HEATER,
            DeviceCategory.HEATER,
        ]:
            entities = [
                SwitcherSensorEntity(coordinator, description)
                for description in HEATER_SENSORS
            ]
            entities.extend(
                SwitcherSensorEntity(coordinator, description)
                for description in DEPRECATED_TIME_SENSORS
                if deprecate_entity(
                    hass,
                    entity_registry,
                    async_on_unload=config_entry.async_on_unload,
                    platform_domain=Platform.SENSOR,
                    entity_unique_id=(
                        f"{coordinator.device_id}-{coordinator.mac_address}"
                        f"-{description.key}"
                    ),
                    issue_id=(
                        f"deprecated_{description.translation_key}"
                        f"_{coordinator.device_id}"
                    ),
                    translation_key=f"deprecated_{description.translation_key}",
                )
            )
            async_add_entities(entities)
        elif coordinator.data.device_type.category is DeviceCategory.THERMOSTAT:
            async_add_entities(
                SwitcherSensorEntity(coordinator, description)
                for description in THERMOSTAT_SENSORS
            )

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_DEVICE_ADD, async_add_sensors)
    )


class SwitcherSensorEntity(SwitcherEntity, SensorEntity):
    """Representation of a Switcher sensor entity."""

    entity_description: SwitcherSensorEntityDescription

    def __init__(
        self,
        coordinator: SwitcherDataUpdateCoordinator,
        description: SwitcherSensorEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_unique_id = (
            f"{coordinator.device_id}-{coordinator.mac_address}-{description.key}"
        )
        self._update_data()

    @override
    def _update_data(self) -> None:
        """Update data from device."""
        value = self.entity_description.value_fn(self.coordinator.data)
        if (
            (variance := self.entity_description.ignored_variance)
            and isinstance(value, datetime)
            and isinstance(self._attr_native_value, datetime)
            and abs(value - self._attr_native_value) < variance
        ):
            return
        self._attr_native_value = value
