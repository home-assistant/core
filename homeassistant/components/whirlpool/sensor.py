"""The Washer/Dryer Sensor for Whirlpool Appliances."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import override


from whirlpool.oven import CavityState, Oven, CookMode
from whirlpool.appliance import Appliance
from whirlpool.washerdryer import MachineState, WasherDryer

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utcnow

from . import WhirlpoolConfigEntry
from .entity import WhirlpoolEntity

SCAN_INTERVAL = timedelta(minutes=5)

WASHER_TANK_FILL = {
    0: "unknown",
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


CYCLE_FUNC = [
    (WasherDryer.get_cycle_status_filling, "cycle_filling"),
    (WasherDryer.get_cycle_status_rinsing, "cycle_rinsing"),
    (WasherDryer.get_cycle_status_sensing, "cycle_sensing"),
    (WasherDryer.get_cycle_status_soaking, "cycle_soaking"),
    (WasherDryer.get_cycle_status_spinning, "cycle_spinning"),
    (WasherDryer.get_cycle_status_washing, "cycle_washing"),
]

OVEN_STATES = [f"oven_{state.name.lower()}" for state in CavityState]
COOK_MODES = [f"cook_{state.name.lower()}" for state in CookMode]

DOOR_OPEN = "door_open"
ICON_O = "mdi:stove"
ICON_D = "mdi:tumble-dryer"
ICON_W = "mdi:washing-machine"

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=5)

STATE_CYCLE_FILLING = "cycle_filling"
STATE_CYCLE_RINSING = "cycle_rinsing"
STATE_CYCLE_SENSING = "cycle_sensing"
STATE_CYCLE_SOAKING = "cycle_soaking"
STATE_CYCLE_SPINNING = "cycle_spinning"
STATE_CYCLE_WASHING = "cycle_washing"
STATE_DOOR_OPEN = "door_open"



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


def oven_state(machine: Oven) -> str | None:
    """Determine correct states for an oven."""

    if machine.get_door_opened():
        return DOOR_OPEN

    return f"oven_{machine.get_cavity_state().name.lower()}"

def cook_mode(machine: Oven) -> str | None:
    """Determine correct states for an oven."""
    return f"cook_{machine.get_cook_mode().name.lower()}"

def is_oven_online(machine: Oven) -> bool:
    """Determine online status of an oven."""
    return machine.get_online()


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
        options=list(WASHER_TANK_FILL.values()),
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

OVEN_SENSORS: tuple[WhirlpoolSensorEntityDescription, ...] = (
    WhirlpoolSensorEntityDescription(
        key="oven_state",
        name="Oven State",
        device_class=SensorDeviceClass.ENUM,
        options=(
            [value for value in OVEN_STATES]
            + [DOOR_OPEN]
        ),
        value_fn=oven_state,
    ),
    WhirlpoolSensorEntityDescription(
        key="cook_mode",
        name="Cook Mode",
        device_class=SensorDeviceClass.ENUM,
        options=COOK_MODES,
        value_fn=cook_mode,
    ),
    WhirlpoolSensorEntityDescription(
        key="online_status",
        name="Status of connection",
        device_class=SensorDeviceClass.ENUM,
        options=[True, False],
        value_fn=is_oven_online,
    ),
)
SENSOR_TIMER: tuple[SensorEntityDescription] = (
    SensorEntityDescription(
        key="timeremaining",
        translation_key="end_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:progress-clock",
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
    for appliance in whirlpool_data.appliances_manager.ovens:
        _ov = Oven(
            whirlpool_data.backend_selector,
            whirlpool_data.auth,
            appliance["SAID"],
            async_get_clientsession(hass),
        )
        await _ov.connect()

        entities.extend(
            [
                OvenClass(
                    appliance["SAID"],
                    appliance["NAME"],
                    description,
                    _ov,
                )
                for description in OVEN_SENSORS
            ]
        )
        entities.extend(
            [
                OvenTimeClass(
                    appliance["SAID"],
                    appliance["NAME"],
                    description,
                    _ov,
                )
                for description in SENSOR_TIMER
            ]
        )
    async_add_entities(entities)


class OvenClass(SensorEntity):
    """A class for the whirlpool/maytag oven account."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        said: str,
        name: str,
        description: WhirlpoolSensorEntityDescription,
        oven: Oven,
    ) -> None:
        """Initialize the oven sensor."""
        self._ov: Oven = oven

        self._attr_icon = ICON_O

        self.entity_description: WhirlpoolSensorEntityDescription = description
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, said)},
            name=name.capitalize(),
            manufacturer="Whirlpool",
        )
        self._attr_unique_id = f"{said}-{description.key}"

    async def async_added_to_hass(self) -> None:
        """Connect oven to the cloud."""
        self._ov.register_attr_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Close Whirlpool Appliance sockets before removing."""
        self._ov.unregister_attr_callback(self.async_write_ha_state)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._ov.get_online()

    @property
    def native_value(self) -> StateType | str:
        """Return native value of sensor."""
        return self.entity_description.value_fn(self._ov)


class OvenTimeClass(RestoreSensor):
    """A timestamp class for the whirlpool/maytag oven account."""

    _attr_should_poll = True
    _attr_has_entity_name = True

    def __init__(
        self,
        said: str,
        name: str,
        description: SensorEntityDescription,
        oven: Oven,
    ) -> None:
        """Initialize the oven sensor."""
        self._ov: Oven = oven

        self._attr_icon = ICON_O

        self.entity_description: SensorEntityDescription = description
        self._running: bool | None = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, said)},
            name=name.capitalize(),
            manufacturer="Whirlpool",
        )
        self._attr_unique_id = f"{said}-{description.key}"

    async def async_added_to_hass(self) -> None:
        """Connect oven to the cloud."""
        if restored_data := await self.async_get_last_sensor_data():
            self._attr_native_value = restored_data.native_value
        await super().async_added_to_hass()
        self._ov.register_attr_callback(self.update_from_latest_data)

    async def async_will_remove_from_hass(self) -> None:
        """Close Whirlpool Appliance sockets before removing."""
        self._ov.unregister_attr_callback(self.update_from_latest_data)
        await self._ov.disconnect()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._ov.get_online()

    async def async_update(self) -> None:
        """Update status of Whirlpool."""
        await self._ov.fetch_data()

    @callback
    def update_from_latest_data(self) -> None:
        """Calculate the time stamp for completion."""
        machine_state = self._ov.get_cavity_state()
        now = utcnow()
        if (
            machine_state is CavityState.Standby
            and self._running
        ):
            self._running = False
            self._attr_native_value = now
            self._async_write_ha_state()

        if machine_state is CavityState.Cooking:
            self._running = True

            new_timestamp = now + timedelta(
                seconds=int(self._ov.get_attribute("OvenUpperCavity_TimeStatusCookTimeRemaining"))
            )

            if (
                self._attr_native_value is None
                or isinstance(self._attr_native_value, datetime)
                and abs(new_timestamp - self._attr_native_value) > timedelta(seconds=60)
            ):
                self._attr_native_value = new_timestamp
                self._async_write_ha_state()


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
