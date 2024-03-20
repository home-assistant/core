"""The Washer/Dryer Sensor for Whirlpool Appliances."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from whirlpool.washerdryer import MachineState, WasherDryer

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utcnow

from . import WhirlpoolData
from .const import DOMAIN

TANK_FILL = {
    "0": "unknown",
    "1": "empty",
    "2": "25",
    "3": "50",
    "4": "100",
    "5": "active",
}

MACHINE_STATE = {
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

DOOR_OPEN = "door_open"
ICON_D = "mdi:tumble-dryer"
ICON_W = "mdi:washing-machine"

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=5)


def washer_state(washer: WasherDryer) -> str | None:
    """Determine correct states for a washer."""

    if washer.get_attribute("Cavity_OpStatusDoorOpen") == "1":
        return DOOR_OPEN

    machine_state = washer.get_machine_state()

    if machine_state == MachineState.RunningMainCycle:
        for func, cycle_name in CYCLE_FUNC:
            if func(washer):
                return cycle_name

    return MACHINE_STATE.get(machine_state)


@dataclass(frozen=True, kw_only=True)
class WhirlpoolSensorEntityDescription(SensorEntityDescription):
    """Describes Whirlpool Washer sensor entity."""

    value_fn: Callable


SENSORS: tuple[WhirlpoolSensorEntityDescription, ...] = (
    WhirlpoolSensorEntityDescription(
        key="state",
        translation_key="whirlpool_machine",
        device_class=SensorDeviceClass.ENUM,
        options=(
            list(MACHINE_STATE.values())
            + [value for _, value in CYCLE_FUNC]
            + [DOOR_OPEN]
        ),
        value_fn=washer_state,
    ),
    WhirlpoolSensorEntityDescription(
        key="DispenseLevel",
        translation_key="whirlpool_tank",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.ENUM,
        options=list(TANK_FILL.values()),
        value_fn=lambda WasherDryer: TANK_FILL.get(
            WasherDryer.get_attribute("WashCavity_OpStatusBulkDispense1Level")
        ),
    ),
)

SENSOR_TIMER: tuple[SensorEntityDescription] = (
    SensorEntityDescription(
        key="timeremaining",
        translation_key="end_time",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Config flow entry for Whrilpool Laundry."""
    entities: list = []
    whirlpool_data: WhirlpoolData = hass.data[DOMAIN][config_entry.entry_id]
    for appliance in whirlpool_data.appliances_manager.washer_dryers:
        _wd = WasherDryer(
            whirlpool_data.backend_selector,
            whirlpool_data.auth,
            appliance["SAID"],
            async_get_clientsession(hass),
        )
        await _wd.connect()

        entities.extend(
            [
                WasherDryerClass(
                    appliance["SAID"],
                    appliance["NAME"],
                    description,
                    _wd,
                )
                for description in SENSORS
            ]
        )
        entities.extend(
            [
                WasherDryerTimeClass(
                    appliance["SAID"],
                    appliance["NAME"],
                    description,
                    _wd,
                )
                for description in SENSOR_TIMER
            ]
        )
    async_add_entities(entities)


class WasherDryerClass(SensorEntity):
    """A class for the whirlpool/maytag washer account."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        said: str,
        name: str,
        description: WhirlpoolSensorEntityDescription,
        washdry: WasherDryer,
    ) -> None:
        """Initialize the washer sensor."""
        self._wd: WasherDryer = washdry

        if name == "dryer":
            self._attr_icon = ICON_D
        else:
            self._attr_icon = ICON_W

        self.entity_description: WhirlpoolSensorEntityDescription = description
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, said)},
            name=name.capitalize(),
            manufacturer="Whirlpool",
        )
        self._attr_unique_id = f"{said}-{description.key}"

    async def async_added_to_hass(self) -> None:
        """Connect washer/dryer to the cloud."""
        self._wd.register_attr_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Close Whirlpool Appliance sockets before removing."""
        self._wd.unregister_attr_callback(self.async_write_ha_state)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._wd.get_online()

    @property
    def native_value(self) -> StateType | str:
        """Return native value of sensor."""
        return self.entity_description.value_fn(self._wd)


class WasherDryerTimeClass(RestoreSensor):
    """A timestamp class for the whirlpool/maytag washer account."""

    _attr_should_poll = True
    _attr_has_entity_name = True

    def __init__(
        self,
        said: str,
        name: str,
        description: SensorEntityDescription,
        washdry: WasherDryer,
    ) -> None:
        """Initialize the washer sensor."""
        self._wd: WasherDryer = washdry

        if name == "dryer":
            self._attr_icon = ICON_D
        else:
            self._attr_icon = ICON_W

        self.entity_description: SensorEntityDescription = description
        self._running: bool | None = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, said)},
            name=name.capitalize(),
            manufacturer="Whirlpool",
        )
        self._attr_unique_id = f"{said}-{description.key}"

    async def async_added_to_hass(self) -> None:
        """Connect washer/dryer to the cloud."""
        if restored_data := await self.async_get_last_sensor_data():
            self._attr_native_value = restored_data.native_value
        await super().async_added_to_hass()
        self._wd.register_attr_callback(self.update_from_latest_data)

    async def async_will_remove_from_hass(self) -> None:
        """Close Whrilpool Appliance sockets before removing."""
        self._wd.unregister_attr_callback(self.update_from_latest_data)
        await self._wd.disconnect()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._wd.get_online()

    async def async_update(self) -> None:
        """Update status of Whirlpool."""
        await self._wd.fetch_data()

    @callback
    def update_from_latest_data(self) -> None:
        """Calculate the time stamp for completion."""
        machine_state = self._wd.get_machine_state()
        now = utcnow()
        if (
            machine_state.value
            in {MachineState.Complete.value, MachineState.Standby.value}
            and self._running
        ):
            self._running = False
            self._attr_native_value = now
            self._async_write_ha_state()

        if machine_state is MachineState.RunningMainCycle:
            self._running = True

            new_timestamp = now + timedelta(
                seconds=int(self._wd.get_attribute("Cavity_TimeStatusEstTimeRemaining"))
            )

            if (
                self._attr_native_value is None
                or isinstance(self._attr_native_value, datetime)
                and abs(new_timestamp - self._attr_native_value) > timedelta(seconds=60)
            ):
                self._attr_native_value = new_timestamp
                self._async_write_ha_state()
