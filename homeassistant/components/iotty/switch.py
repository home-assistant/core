"""Implement a iotty Light Switch Device."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any, Generic, TypeVar

from iottycloud.device import Device
from iottycloud.lightswitch import LightSwitch
from iottycloud.outlet import Outlet
from iottycloud.verbs import (
    COMMAND_TURNOFF,
    COMMAND_TURNON,
    LS_DEVICE_TYPE_UID,
    OU_DEVICE_TYPE_UID,
)

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IottyConfigEntry
from .api import IottyProxy
from .coordinator import IottyDataUpdateCoordinator
from .entity import IottyEntity

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T", bound=Device)


@dataclass(frozen=True, kw_only=True)
class IottySwitchEntityDescription(
    Generic[T],
    SwitchEntityDescription,
):
    """Description of a iotty Switch."""

    control_fn: Callable[[IottyProxy, T, str], Coroutine[Any, Any, Any]]
    is_on_fn: Callable[[T], bool]
    set_is_on_fn: Callable[[T, T], Any]


def _control_lightswitch(
    cloud: IottyProxy, lightswitch: LightSwitch, command_code: str
) -> Coroutine[Any, Any, Any]:
    return cloud.command(lightswitch.device_id, command_code)


def _is_on_lightswitch(lightswitch: LightSwitch) -> bool:
    return lightswitch.is_on


def _set_is_on_lightswitch(
    lightswitch: LightSwitch, updated_lightswitch: LightSwitch
) -> Any:
    lightswitch.is_on = updated_lightswitch.is_on


def _control_outlet(
    cloud: IottyProxy, outlet: Outlet, command_code: str
) -> Coroutine[Any, Any, bool]:
    return cloud.command(outlet.device_id, command_code)


def _is_on_outlet(outlet: Outlet) -> bool:
    return outlet.is_on


def _set_is_on_outlet(outlet: Outlet, updated_outlet: Outlet) -> Any:
    outlet.is_on = updated_outlet.is_on


ENTITIES: tuple[IottySwitchEntityDescription, ...] = (
    IottySwitchEntityDescription(
        key="light",
        name=None,
        control_fn=_control_lightswitch,
        is_on_fn=_is_on_lightswitch,
        set_is_on_fn=_set_is_on_lightswitch,
        device_class=SwitchDeviceClass.SWITCH,
    ),
    IottySwitchEntityDescription(
        key="outlet",
        name=None,
        control_fn=_control_outlet,
        is_on_fn=_is_on_outlet,
        set_is_on_fn=_set_is_on_outlet,
        device_class=SwitchDeviceClass.OUTLET,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: IottyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Activate the iotty Switch component."""
    _LOGGER.debug("Setup SWITCH entry id is %s", config_entry.entry_id)

    coordinator = config_entry.runtime_data.coordinator
    lightswitch_entities = [
        IottySwitch(
            coordinator=coordinator,
            iotty_cloud=coordinator.iotty,
            iotty_device=d,
            entity_description=ENTITIES[0],
        )
        for d in coordinator.data.devices
        if d.device_type == LS_DEVICE_TYPE_UID
        if (isinstance(d, LightSwitch))
    ]
    _LOGGER.debug("Found %d LightSwitches", len(lightswitch_entities))

    outlet_entities = [
        IottySwitch(
            coordinator=coordinator,
            iotty_cloud=coordinator.iotty,
            iotty_device=d,
            entity_description=ENTITIES[1],
        )
        for d in coordinator.data.devices
        if d.device_type == OU_DEVICE_TYPE_UID
        if (isinstance(d, Outlet))
    ]
    _LOGGER.debug("Found %d Outlets", len(outlet_entities))

    entities = lightswitch_entities + outlet_entities

    async_add_entities(entities)

    known_devices: set = config_entry.runtime_data.known_devices
    for known_device in coordinator.data.devices:
        if known_device.device_type in {LS_DEVICE_TYPE_UID, OU_DEVICE_TYPE_UID}:
            known_devices.add(known_device)

    @callback
    def async_update_data() -> None:
        """Handle updated data from the API endpoint."""
        if not coordinator.last_update_success:
            return

        devices = coordinator.data.devices
        entities = []
        known_devices: set = config_entry.runtime_data.known_devices

        # Add entities for devices which we've not yet seen
        for device in devices:
            if any(d.device_id == device.device_id for d in known_devices) or (
                device.device_type not in {LS_DEVICE_TYPE_UID, OU_DEVICE_TYPE_UID}
            ):
                continue

            iotty_entity: SwitchEntity
            if device.device_type == LS_DEVICE_TYPE_UID:
                iotty_entity = IottySwitch(
                    coordinator=coordinator,
                    iotty_cloud=coordinator.iotty,
                    iotty_device=LightSwitch(
                        device.device_id,
                        device.serial_number,
                        device.device_type,
                        device.device_name,
                    ),
                    entity_description=ENTITIES[0],
                )
            else:
                iotty_entity = IottySwitch(
                    coordinator=coordinator,
                    iotty_cloud=coordinator.iotty,
                    iotty_device=Outlet(
                        device.device_id,
                        device.serial_number,
                        device.device_type,
                        device.device_name,
                    ),
                    entity_description=ENTITIES[1],
                )

            entities.extend([iotty_entity])
            known_devices.add(device)

        async_add_entities(entities)

    # Add a subscriber to the coordinator to discover new devices
    coordinator.async_add_listener(async_update_data)


class IottySwitch(IottyEntity, SwitchEntity):
    """Haas entity class for iotty switch."""

    entity_description: IottySwitchEntityDescription
    _attr_device_class: SwitchDeviceClass | None
    _iotty_device: Device

    def __init__(
        self,
        coordinator: IottyDataUpdateCoordinator,
        iotty_cloud: IottyProxy,
        iotty_device: Device,
        entity_description: IottySwitchEntityDescription,
    ) -> None:
        """Initialize the Switch device."""
        super().__init__(coordinator, iotty_cloud, iotty_device)
        self.entity_description = entity_description
        # print(entity_description.device_class)
        self._attr_device_class = entity_description.device_class

    @property
    def is_on(self) -> bool:
        """Return true if the Switch is on."""
        _LOGGER.debug(
            "Retrieve device status for %s ? %s",
            self._iotty_device.device_id,
            self.entity_description.is_on_fn(self._iotty_device),
        )
        return self.entity_description.is_on_fn(self._iotty_device)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the Switch on."""
        _LOGGER.debug("[%s] Turning on", self._iotty_device.device_id)
        await self.entity_description.control_fn(
            self._iotty_cloud, self._iotty_device, COMMAND_TURNON
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the Switch off."""
        _LOGGER.debug("[%s] Turning off", self._iotty_device.device_id)
        await self.entity_description.control_fn(
            self._iotty_cloud, self._iotty_device, COMMAND_TURNOFF
        )
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        device: Device = next(
            device
            for device in self.coordinator.data.devices
            if device.device_id == self._iotty_device.device_id
        )
        self.entity_description.set_is_on_fn(self._iotty_device, device)
        self.async_write_ha_state()
