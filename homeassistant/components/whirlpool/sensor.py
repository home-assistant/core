"""The Washer/Dryer Sensor for Whirlpool Appliances."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import override

from whirlpool.appliance import Appliance
from whirlpool.dryer import Dryer, MachineState as DryerMachineState
from whirlpool.oven import (
    Cavity as OvenCavity,
    CavityState as OvenCavityState,
    CookMode,
    Oven,
)
from whirlpool.washer import MachineState as WasherMachineState, Washer

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utcnow

from . import WhirlpoolConfigEntry
from .entity import WhirlpoolEntity, WhirlpoolOvenEntity

PARALLEL_UPDATES = 1
SCAN_INTERVAL = timedelta(minutes=5)

WASHER_TANK_FILL = {
    0: None,
    1: "empty",
    2: "25",
    3: "50",
    4: "100",
    5: "active",
}

WASHER_MACHINE_STATE = {
    WasherMachineState.Standby: "standby",
    WasherMachineState.Setting: "setting",
    WasherMachineState.DelayCountdownMode: "delay_countdown",
    WasherMachineState.DelayPause: "delay_paused",
    WasherMachineState.SmartDelay: "smart_delay",
    WasherMachineState.SmartGridPause: "smart_grid_pause",
    WasherMachineState.Pause: "pause",
    WasherMachineState.RunningMainCycle: "running_maincycle",
    WasherMachineState.RunningPostCycle: "running_postcycle",
    WasherMachineState.Exceptions: "exception",
    WasherMachineState.Complete: "complete",
    WasherMachineState.PowerFailure: "power_failure",
    WasherMachineState.ServiceDiagnostic: "service_diagnostic_mode",
    WasherMachineState.FactoryDiagnostic: "factory_diagnostic_mode",
    WasherMachineState.LifeTest: "life_test",
    WasherMachineState.CustomerFocusMode: "customer_focus_mode",
    WasherMachineState.DemoMode: "demo_mode",
    WasherMachineState.HardStopOrError: "hard_stop_or_error",
    WasherMachineState.SystemInit: "system_initialize",
}

DRYER_MACHINE_STATE = {
    DryerMachineState.Standby: "standby",
    DryerMachineState.Setting: "setting",
    DryerMachineState.DelayCountdownMode: "delay_countdown",
    DryerMachineState.DelayPause: "delay_paused",
    DryerMachineState.SmartDelay: "smart_delay",
    DryerMachineState.SmartGridPause: "smart_grid_pause",
    DryerMachineState.Pause: "pause",
    DryerMachineState.RunningMainCycle: "running_maincycle",
    DryerMachineState.RunningPostCycle: "running_postcycle",
    DryerMachineState.Exceptions: "exception",
    DryerMachineState.Complete: "complete",
    DryerMachineState.PowerFailure: "power_failure",
    DryerMachineState.ServiceDiagnostic: "service_diagnostic_mode",
    DryerMachineState.FactoryDiagnostic: "factory_diagnostic_mode",
    DryerMachineState.LifeTest: "life_test",
    DryerMachineState.CustomerFocusMode: "customer_focus_mode",
    DryerMachineState.DemoMode: "demo_mode",
    DryerMachineState.HardStopOrError: "hard_stop_or_error",
    DryerMachineState.SystemInit: "system_initialize",
    DryerMachineState.Cancelled: "cancelled",
}

STATE_CYCLE_FILLING = "cycle_filling"
STATE_CYCLE_RINSING = "cycle_rinsing"
STATE_CYCLE_SENSING = "cycle_sensing"
STATE_CYCLE_SOAKING = "cycle_soaking"
STATE_CYCLE_SPINNING = "cycle_spinning"
STATE_CYCLE_WASHING = "cycle_washing"

OVEN_CAVITY_STATE = {
    OvenCavityState.Standby: "standby",
    OvenCavityState.Preheating: "preheating",
    OvenCavityState.Cooking: "cooking",
}

OVEN_COOK_MODE = {
    CookMode.Standby: "standby",
    CookMode.Bake: "bake",
    CookMode.ConvectBake: "convection_bake",
    CookMode.Broil: "broil",
    CookMode.ConvectBroil: "convection_broil",
    CookMode.ConvectRoast: "convection_roast",
    CookMode.KeepWarm: "keep_warm",
    CookMode.AirFry: "air_fry",
}


def washer_state(washer: Washer) -> str | None:
    """Determine correct states for a washer."""

    machine_state = washer.get_machine_state()

    if machine_state == WasherMachineState.RunningMainCycle:
        if washer.get_cycle_status_filling():
            return STATE_CYCLE_FILLING
        if washer.get_cycle_status_rinsing():
            return STATE_CYCLE_RINSING
        if washer.get_cycle_status_sensing():
            return STATE_CYCLE_SENSING
        if washer.get_cycle_status_soaking():
            return STATE_CYCLE_SOAKING
        if washer.get_cycle_status_spinning():
            return STATE_CYCLE_SPINNING
        if washer.get_cycle_status_washing():
            return STATE_CYCLE_WASHING

    return WASHER_MACHINE_STATE.get(machine_state)


def dryer_state(dryer: Dryer) -> str | None:
    """Determine correct states for a dryer."""

    machine_state = dryer.get_machine_state()

    if machine_state == DryerMachineState.RunningMainCycle:
        if dryer.get_cycle_status_sensing():
            return STATE_CYCLE_SENSING

    return DRYER_MACHINE_STATE.get(machine_state)


@dataclass(frozen=True, kw_only=True)
class WhirlpoolSensorEntityDescription(SensorEntityDescription):
    """Describes a Whirlpool sensor entity."""

    value_fn: Callable[[Appliance], str | None]


WASHER_STATE_OPTIONS = [
    *WASHER_MACHINE_STATE.values(),
    STATE_CYCLE_FILLING,
    STATE_CYCLE_RINSING,
    STATE_CYCLE_SENSING,
    STATE_CYCLE_SOAKING,
    STATE_CYCLE_SPINNING,
    STATE_CYCLE_WASHING,
]

DRYER_STATE_OPTIONS = [
    *DRYER_MACHINE_STATE.values(),
    STATE_CYCLE_SENSING,
]

WASHER_SENSORS: tuple[WhirlpoolSensorEntityDescription, ...] = (
    WhirlpoolSensorEntityDescription(
        key="state",
        translation_key="washer_state",
        device_class=SensorDeviceClass.ENUM,
        options=WASHER_STATE_OPTIONS,
        value_fn=washer_state,
    ),
    WhirlpoolSensorEntityDescription(
        key="DispenseLevel",
        translation_key="whirlpool_tank",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.ENUM,
        options=[value for value in WASHER_TANK_FILL.values() if value],
        value_fn=lambda washer: WASHER_TANK_FILL.get(washer.get_dispense_1_level()),
    ),
)

DRYER_SENSORS: tuple[WhirlpoolSensorEntityDescription, ...] = (
    WhirlpoolSensorEntityDescription(
        key="state",
        translation_key="dryer_state",
        device_class=SensorDeviceClass.ENUM,
        options=DRYER_STATE_OPTIONS,
        value_fn=dryer_state,
    ),
)

WASHER_DRYER_TIME_SENSORS: tuple[SensorEntityDescription] = (
    SensorEntityDescription(
        key="timeremaining",
        translation_key="end_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:progress-clock",
    ),
)


@dataclass(frozen=True, kw_only=True)
class WhirlpoolOvenCavitySensorEntityDescription(SensorEntityDescription):
    """Describes a Whirlpool oven cavity sensor entity."""

    value_fn: Callable[[Oven, OvenCavity], str | int | float | None]


OVEN_CAVITY_SENSORS: tuple[WhirlpoolOvenCavitySensorEntityDescription, ...] = (
    WhirlpoolOvenCavitySensorEntityDescription(
        key="oven_state",
        translation_key="oven_state",
        device_class=SensorDeviceClass.ENUM,
        options=list(OVEN_CAVITY_STATE.values()),
        value_fn=lambda oven, cavity: (
            OVEN_CAVITY_STATE.get(state)
            if (state := oven.get_cavity_state(cavity)) is not None
            else None
        ),
    ),
    WhirlpoolOvenCavitySensorEntityDescription(
        key="oven_cook_mode",
        translation_key="oven_cook_mode",
        device_class=SensorDeviceClass.ENUM,
        options=list(OVEN_COOK_MODE.values()),
        value_fn=lambda oven, cavity: (
            OVEN_COOK_MODE.get(cook_mode)
            if (cook_mode := oven.get_cook_mode(cavity)) is not None
            else None
        ),
    ),
    WhirlpoolOvenCavitySensorEntityDescription(
        key="oven_current_temperature",
        translation_key="oven_current_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda oven, cavity: (
            temp if (temp := oven.get_temp(cavity)) != 0 else None
        ),
    ),
    WhirlpoolOvenCavitySensorEntityDescription(
        key="oven_target_temperature",
        translation_key="oven_target_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda oven, cavity: (
            temp if (temp := oven.get_target_temp(cavity)) != 0 else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WhirlpoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Config flow entry for Whirlpool sensors."""
    appliances_manager = config_entry.runtime_data

    washer_sensors = [
        WhirlpoolSensor(washer, description)
        for washer in appliances_manager.washers
        for description in WASHER_SENSORS
    ]

    washer_time_sensors = [
        WasherTimeSensor(washer, description)
        for washer in appliances_manager.washers
        for description in WASHER_DRYER_TIME_SENSORS
    ]

    dryer_sensors = [
        WhirlpoolSensor(dryer, description)
        for dryer in appliances_manager.dryers
        for description in DRYER_SENSORS
    ]

    dryer_time_sensors = [
        DryerTimeSensor(dryer, description)
        for dryer in appliances_manager.dryers
        for description in WASHER_DRYER_TIME_SENSORS
    ]

    oven_upper_cavity_sensors = [
        WhirlpoolOvenCavitySensor(oven, OvenCavity.Upper, description)
        for oven in appliances_manager.ovens
        if oven.get_oven_cavity_exists(OvenCavity.Upper)
        for description in OVEN_CAVITY_SENSORS
    ]

    oven_lower_cavity_sensors = [
        WhirlpoolOvenCavitySensor(oven, OvenCavity.Lower, description)
        for oven in appliances_manager.ovens
        if oven.get_oven_cavity_exists(OvenCavity.Lower)
        for description in OVEN_CAVITY_SENSORS
    ]

    async_add_entities(
        [
            *washer_sensors,
            *washer_time_sensors,
            *dryer_sensors,
            *dryer_time_sensors,
            *oven_upper_cavity_sensors,
            *oven_lower_cavity_sensors,
        ]
    )


class WhirlpoolSensor(WhirlpoolEntity, SensorEntity):
    """A class for the Whirlpool sensors."""

    def __init__(
        self, appliance: Appliance, description: WhirlpoolSensorEntityDescription
    ) -> None:
        """Initialize the washer sensor."""
        super().__init__(appliance, unique_id_suffix=f"-{description.key}")
        self.entity_description: WhirlpoolSensorEntityDescription = description

    @property
    def native_value(self) -> StateType | str:
        """Return native value of sensor."""
        return self.entity_description.value_fn(self._appliance)


class WasherDryerTimeSensorBase(WhirlpoolEntity, RestoreSensor, ABC):
    """Abstract base class for Whirlpool washer/dryer time sensors."""

    _attr_should_poll = True
    _appliance: Washer | Dryer

    def __init__(
        self, appliance: Washer | Dryer, description: SensorEntityDescription
    ) -> None:
        """Initialize the washer/dryer sensor."""
        super().__init__(appliance, unique_id_suffix=f"-{description.key}")
        self.entity_description = description

        self._running: bool | None = None
        self._value: datetime | None = None

    @abstractmethod
    def _is_machine_state_finished(self) -> bool:
        """Return true if the machine is in a finished state."""

    @abstractmethod
    def _is_machine_state_running(self) -> bool:
        """Return true if the machine is in a running state."""

    async def async_added_to_hass(self) -> None:
        """Register attribute updates callback."""
        if restored_data := await self.async_get_last_sensor_data():
            if isinstance(restored_data.native_value, datetime):
                self._value = restored_data.native_value
        await super().async_added_to_hass()

    async def async_update(self) -> None:
        """Update status of Whirlpool."""
        await self._appliance.fetch_data()

    @override
    @property
    def native_value(self) -> datetime | None:
        """Calculate the time stamp for completion."""
        now = utcnow()

        if self._is_machine_state_finished() and self._running:
            self._running = False
            self._value = now

        if self._is_machine_state_running():
            self._running = True
            new_timestamp = now + timedelta(
                seconds=self._appliance.get_time_remaining()
            )
            if self._value is None or (
                isinstance(self._value, datetime)
                and abs(new_timestamp - self._value) > timedelta(seconds=60)
            ):
                self._value = new_timestamp
        return self._value


class WasherTimeSensor(WasherDryerTimeSensorBase):
    """A timestamp class for Whirlpool washers."""

    _appliance: Washer

    def _is_machine_state_finished(self) -> bool:
        """Return true if the machine is in a finished state."""
        return self._appliance.get_machine_state() in {
            WasherMachineState.Complete,
            WasherMachineState.Standby,
        }

    def _is_machine_state_running(self) -> bool:
        """Return true if the machine is in a running state."""
        return (
            self._appliance.get_machine_state() is WasherMachineState.RunningMainCycle
        )


class DryerTimeSensor(WasherDryerTimeSensorBase):
    """A timestamp class for Whirlpool dryers."""

    _appliance: Dryer

    def _is_machine_state_finished(self) -> bool:
        """Return true if the machine is in a finished state."""
        return self._appliance.get_machine_state() in {
            DryerMachineState.Complete,
            DryerMachineState.Standby,
        }

    def _is_machine_state_running(self) -> bool:
        """Return true if the machine is in a running state."""
        return self._appliance.get_machine_state() is DryerMachineState.RunningMainCycle


class WhirlpoolOvenCavitySensor(WhirlpoolOvenEntity, SensorEntity):
    """A class for Whirlpool oven cavity sensors."""

    def __init__(
        self,
        oven: Oven,
        cavity: OvenCavity,
        description: WhirlpoolOvenCavitySensorEntityDescription,
    ) -> None:
        """Initialize the oven cavity sensor."""
        super().__init__(
            oven, cavity, description.translation_key, f"-{description.key}"
        )
        self.entity_description: WhirlpoolOvenCavitySensorEntityDescription = (
            description
        )

    @property
    def native_value(self) -> StateType:
        """Return native value of sensor."""
        return self.entity_description.value_fn(self._appliance, self.cavity)
