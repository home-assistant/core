"""The Washer/Dryer Sensor for Whirlpool Appliances."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import override

from whirlpool.appliance import Appliance
from whirlpool.oven import CAVITY_PREFIX_MAP, Cavity, CavityState, CookMode, Oven
from whirlpool.washerdryer import MachineState, WasherDryer

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

SCAN_INTERVAL = timedelta(minutes=5)

WASHER_TANK_FILL = {
    0: None,
    1: "empty",
    2: "25",
    3: "50",
    4: "100",
    5: "active",
}

WASHER_DRYER_MACHINE_STATE = {
    MachineState.Standby: "standby",
    MachineState.Setting: "setting",
    MachineState.DelayCountdownMode: "delay_countdown",
    MachineState.DelayPause: "delay_paused",
    MachineState.SmartDelay: "smart_delay",
    MachineState.SmartGridPause: "smart_grid_pause",
    MachineState.Pause: "pause",
    MachineState.RunningMainCycle: "running_maincycle",
    MachineState.RunningPostCycle: "running_postcycle",
    MachineState.Exceptions: "exception",
    MachineState.Complete: "complete",
    MachineState.PowerFailure: "power_failure",
    MachineState.ServiceDiagnostic: "service_diagnostic_mode",
    MachineState.FactoryDiagnostic: "factory_diagnostic_mode",
    MachineState.LifeTest: "life_test",
    MachineState.CustomerFocusMode: "customer_focus_mode",
    MachineState.DemoMode: "demo_mode",
    MachineState.HardStopOrError: "hard_stop_or_error",
    MachineState.SystemInit: "system_initialize",
}

STATE_CYCLE_FILLING = "cycle_filling"
STATE_CYCLE_RINSING = "cycle_rinsing"
STATE_CYCLE_SENSING = "cycle_sensing"
STATE_CYCLE_SOAKING = "cycle_soaking"
STATE_CYCLE_SPINNING = "cycle_spinning"
STATE_CYCLE_WASHING = "cycle_washing"
STATE_DOOR_OPEN = "door_open"

OVEN_CAVITY_STATE = {
    CavityState.Standby: "standby",
    CavityState.Preheating: "preheating",
    CavityState.Cooking: "cooking",
    CavityState.NotPresent: "not_present",
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


def washer_dryer_state(washer_dryer: WasherDryer) -> str | None:
    """Determine correct states for a washer/dryer."""

    if washer_dryer.get_door_open():
        return STATE_DOOR_OPEN

    machine_state = washer_dryer.get_machine_state()

    if machine_state == MachineState.RunningMainCycle:
        if washer_dryer.get_cycle_status_filling():
            return STATE_CYCLE_FILLING
        if washer_dryer.get_cycle_status_rinsing():
            return STATE_CYCLE_RINSING
        if washer_dryer.get_cycle_status_sensing():
            return STATE_CYCLE_SENSING
        if washer_dryer.get_cycle_status_soaking():
            return STATE_CYCLE_SOAKING
        if washer_dryer.get_cycle_status_spinning():
            return STATE_CYCLE_SPINNING
        if washer_dryer.get_cycle_status_washing():
            return STATE_CYCLE_WASHING

    return WASHER_DRYER_MACHINE_STATE.get(machine_state)


@dataclass(frozen=True, kw_only=True)
class WhirlpoolSensorEntityDescription(SensorEntityDescription):
    """Describes a Whirlpool sensor entity."""

    value_fn: Callable[[Appliance], str | None]


WASHER_DRYER_STATE_OPTIONS = [
    *WASHER_DRYER_MACHINE_STATE.values(),
    STATE_CYCLE_FILLING,
    STATE_CYCLE_RINSING,
    STATE_CYCLE_SENSING,
    STATE_CYCLE_SOAKING,
    STATE_CYCLE_SPINNING,
    STATE_CYCLE_WASHING,
    STATE_DOOR_OPEN,
]

WASHER_SENSORS: tuple[WhirlpoolSensorEntityDescription, ...] = (
    WhirlpoolSensorEntityDescription(
        key="state",
        translation_key="washer_state",
        device_class=SensorDeviceClass.ENUM,
        options=WASHER_DRYER_STATE_OPTIONS,
        value_fn=washer_dryer_state,
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
        options=WASHER_DRYER_STATE_OPTIONS,
        value_fn=washer_dryer_state,
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

    value_fn: Callable[[Oven, Cavity], str | int | float | None]


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

OVEN_CAVITY_TIME_SENSORS: tuple[WhirlpoolOvenCavitySensorEntityDescription] = (
    WhirlpoolOvenCavitySensorEntityDescription(
        key="oven_end_time",
        translation_key="oven_end_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:progress-clock",
        value_fn=lambda oven, cavity: (None),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WhirlpoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Config flow entry for Whirlpool sensors."""
    entities: list = []
    appliances_manager = config_entry.runtime_data
    for washer_dryer in appliances_manager.washer_dryers:
        sensor_descriptions = (
            DRYER_SENSORS
            if "dryer" in washer_dryer.appliance_info.data_model.lower()
            else WASHER_SENSORS
        )

        entities.extend(
            WhirlpoolSensor(washer_dryer, description)
            for description in sensor_descriptions
        )
        entities.extend(
            WasherDryerTimeSensor(washer_dryer, description)
            for description in WASHER_DRYER_TIME_SENSORS
        )
    for oven in appliances_manager.ovens:
        cavities = []
        if oven.get_oven_cavity_exists(Cavity.Upper):
            cavities.append(Cavity.Upper)
        if oven.get_oven_cavity_exists(Cavity.Lower):
            cavities.append(Cavity.Lower)
        entities.extend(
            WhirlpoolOvenCavitySensor(oven, cavity, description)
            for cavity in cavities
            for description in OVEN_CAVITY_SENSORS
        )
        entities.extend(
            WhirlpoolOvenCavityTimeSensor(oven, cavity, description)
            for cavity in cavities
            for description in OVEN_CAVITY_TIME_SENSORS
        )
    async_add_entities(entities)


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


class WasherDryerTimeSensor(WhirlpoolEntity, RestoreSensor):
    """A timestamp class for the Whirlpool washer/dryer."""

    _attr_should_poll = True

    def __init__(
        self, washer_dryer: WasherDryer, description: SensorEntityDescription
    ) -> None:
        """Initialize the washer sensor."""
        super().__init__(washer_dryer, unique_id_suffix=f"-{description.key}")
        self.entity_description = description

        self._wd = washer_dryer
        self._running: bool | None = None
        self._value: datetime | None = None

    async def async_added_to_hass(self) -> None:
        """Register attribute updates callback."""
        if restored_data := await self.async_get_last_sensor_data():
            if isinstance(restored_data.native_value, datetime):
                self._value = restored_data.native_value
        await super().async_added_to_hass()

    async def async_update(self) -> None:
        """Update status of Whirlpool."""
        await self._wd.fetch_data()

    @override
    @property
    def native_value(self) -> datetime | None:
        """Calculate the time stamp for completion."""
        machine_state = self._wd.get_machine_state()
        now = utcnow()
        if (
            machine_state.value
            in {MachineState.Complete.value, MachineState.Standby.value}
            and self._running
        ):
            self._running = False
            self._value = now

        if machine_state is MachineState.RunningMainCycle:
            self._running = True
            new_timestamp = now + timedelta(seconds=self._wd.get_time_remaining())
            if self._value is None or (
                isinstance(self._value, datetime)
                and abs(new_timestamp - self._value) > timedelta(seconds=60)
            ):
                self._value = new_timestamp
        return self._value


class WhirlpoolOvenCavitySensor(WhirlpoolOvenEntity, SensorEntity):
    """A class for Whirlpool oven cavity sensors."""

    def __init__(
        self,
        oven: Oven,
        cavity: Cavity,
        description: WhirlpoolOvenCavitySensorEntityDescription,
    ) -> None:
        """Initialize the oven cavity sensor."""
        super().__init__(oven)
        cavity_key_suffix = self.get_cavity_key_suffix(cavity)
        self.cavity = cavity
        self.entity_description: WhirlpoolOvenCavitySensorEntityDescription = (
            description
        )
        self._attr_unique_id = f"{oven.said}_{description.key}{cavity_key_suffix}"
        self._attr_translation_key = f"{description.key}{cavity_key_suffix}"
        self._attr_device_class = getattr(description, "device_class", None)
        self._attr_state_class = getattr(description, "state_class", None)
        self._attr_native_unit_of_measurement = getattr(
            description, "native_unit_of_measurement", None
        )
        self._attr_options = getattr(description, "options", None)

    @property
    def native_value(self) -> StateType | str | int | float | None:
        """Return native value of sensor."""
        return self.entity_description.value_fn(self.oven, self.cavity)


class WhirlpoolOvenCavityTimeSensor(WhirlpoolOvenEntity, RestoreSensor):
    """A timestamp class for a Whirlpool oven cavity."""

    _attr_should_poll = True

    def __init__(
        self,
        oven: Oven,
        cavity: Cavity,
        description: WhirlpoolOvenCavitySensorEntityDescription,
    ) -> None:
        """Initialize the oven cavity time sensor."""
        super().__init__(oven)
        cavity_key_suffix = self.get_cavity_key_suffix(cavity)
        self.cavity = cavity
        self.entity_description: WhirlpoolOvenCavitySensorEntityDescription = (
            description
        )
        self._attr_unique_id = f"{oven.said}_{description.key}{cavity_key_suffix}"
        self._attr_translation_key = f"{description.key}{cavity_key_suffix}"
        self.cook_time_duration: int = 0
        self.cook_time_elapsed: int = 0
        self.value: datetime | None = None

    async def async_added_to_hass(self) -> None:
        """Register attribute updates callback."""
        restored_data = await self.async_get_last_sensor_data()
        if restored_data and isinstance(restored_data.native_value, datetime):
            self.value = restored_data.native_value
        self.oven.register_attr_callback(self.on_attr_change)
        await super().async_added_to_hass()

    def on_attr_change(self) -> None:
        """Handle attribute changes."""
        now = utcnow()
        cook_time_duration = self.oven._get_attribute(  # noqa: SLF001
            f"{CAVITY_PREFIX_MAP[self.cavity]}_TimeSetCookTimeSet"
        )
        cook_time_duration = int(cook_time_duration) if cook_time_duration else 0

        # If the duration of the timed cook changed, then recalculate a new end time
        if self.cook_time_duration != cook_time_duration:
            # Calculate the end time if the duration is not None or 0
            if cook_time_duration:
                self.value = now + timedelta(seconds=cook_time_duration)
            elif cook_time_duration == 0:
                # If the duration changed to 0, then we know the timed cook ended
                self.value = now
            self.cook_time_duration = cook_time_duration

        cook_time_elapsed = self.oven.get_cook_time(self.cavity)

        # If the elapsed time of the timed cook changed, then we know a timed cook is underway
        if self.cook_time_elapsed != cook_time_elapsed:
            # If the sensor value is in the past, but the elapsed time is not None, then
            # we know a timed cook started while Home Assistant was not running.  Since we
            # don't know when the cook started, we will set the end time to None.
            if self.value and self.value < now and cook_time_elapsed:
                self.value = None
            self.cook_time_elapsed = cook_time_elapsed

    async def async_update(self) -> None:
        """Update status of the oven."""
        await self.oven.fetch_data()

    @property
    def native_value(self) -> datetime | None:
        """Calculate the time stamp for completion."""
        return self.value
