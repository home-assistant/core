"""Implement a iotty Light Switch Device."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

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
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import IottyProxy
from .coordinator import IottyConfigEntry, IottyDataUpdateCoordinator
from .entity import IottyEntity

_LOGGER = logging.getLogger(__name__)

ENTITIES: dict[str, SwitchEntityDescription] = {
    LS_DEVICE_TYPE_UID: SwitchEntityDescription(
        key="light",
        name=None,
        device_class=SwitchDeviceClass.SWITCH,
    ),
    OU_DEVICE_TYPE_UID: SwitchEntityDescription(
        key="outlet",
        name=None,
        device_class=SwitchDeviceClass.OUTLET,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: IottyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Activate the iotty Switch component."""
    _LOGGER.debug("Setup SWITCH entry id is %s", config_entry.entry_id)

    coordinator = config_entry.runtime_data.coordinator
    lightswitch_entities = [
        IottySwitch(
            coordinator=coordinator,
            iotty_cloud=coordinator.iotty,
            iotty_device=d,
            entity_description=ENTITIES[LS_DEVICE_TYPE_UID],
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
            entity_description=ENTITIES[OU_DEVICE_TYPE_UID],
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
            iotty_device: LightSwitch | Outlet
            if device.device_type == LS_DEVICE_TYPE_UID:
                if TYPE_CHECKING:
                    assert isinstance(device, LightSwitch)
                iotty_device = LightSwitch(
                    device.device_id,
                    device.serial_number,
                    device.device_type,
                    device.device_name,
                )
            else:
                if TYPE_CHECKING:
                    assert isinstance(device, Outlet)
                iotty_device = Outlet(
                    device.device_id,
                    device.serial_number,
                    device.device_type,
                    device.device_name,
                )

            iotty_entity = IottySwitch(
                coordinator=coordinator,
                iotty_cloud=coordinator.iotty,
                iotty_device=iotty_device,
                entity_description=ENTITIES[device.device_type],
            )

            entities.extend([iotty_entity])
            known_devices.add(device)

        async_add_entities(entities)

    # Add a subscriber to the coordinator to discover new devices
    coordinator.async_add_listener(async_update_data)


class IottySwitch(IottyEntity, SwitchEntity):
    """Haas entity class for iotty switch."""

    _attr_device_class: SwitchDeviceClass | None
    _iotty_device: LightSwitch | Outlet

    def __init__(
        self,
        coordinator: IottyDataUpdateCoordinator,
        iotty_cloud: IottyProxy,
        iotty_device: LightSwitch | Outlet,
        entity_description: SwitchEntityDescription,
    ) -> None:
        """Initialize the Switch device."""
        super().__init__(coordinator, iotty_cloud, iotty_device)
        self.entity_description = entity_description
        self._attr_device_class = entity_description.device_class

    @property
    def is_on(self) -> bool:
        """Return true if the Switch is on."""
        _LOGGER.debug(
            "Retrieve device status for %s ? %s",
            self._iotty_device.device_id,
            self._iotty_device.is_on,
        )
        return self._iotty_device.is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the Switch on."""
        _LOGGER.debug("[%s] Turning on", self._iotty_device.device_id)
        await self._iotty_cloud.command(self._iotty_device.device_id, COMMAND_TURNON)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the Switch off."""
        _LOGGER.debug("[%s] Turning off", self._iotty_device.device_id)
        await self._iotty_cloud.command(self._iotty_device.device_id, COMMAND_TURNOFF)
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        device: LightSwitch | Outlet = next(  # type: ignore[assignment]
            device
            for device in self.coordinator.data.devices
            if device.device_id == self._iotty_device.device_id
        )
        self._iotty_device.is_on = device.is_on
        self.async_write_ha_state()
