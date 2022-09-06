"""Binary sensor to read Proxmox VE data."""

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import COORDINATORS, DOMAIN, ProxmoxEntity, device_info
from .const import CONF_LXC, CONF_NODE, CONF_QEMU, ProxmoxType

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors."""

    sensors = []
    coordinators = hass.data[DOMAIN][config_entry.entry_id][COORDINATORS]

    for vm_id in config_entry.data[CONF_QEMU]:
        coordinator = coordinators[config_entry.data[CONF_NODE]][vm_id]

        # unfound vm case
        if coordinator.data is None:
            continue

        vm_sensor = create_binary_sensor(
            coordinator=coordinator,
            vm_id=vm_id,
            key="status",
            name="Status",
            config_entry=config_entry,
            info_device=device_info(
                hass=hass,
                config_entry=config_entry,
                proxmox_type=ProxmoxType.QEMU,
                vm_id=vm_id,
            ),
        )
        sensors.append(vm_sensor)

    for container_id in config_entry.data[CONF_LXC]:
        coordinator = coordinators[config_entry.data[CONF_NODE]][container_id]

        # unfound container case
        if coordinator.data is None:
            continue

        container_sensor = create_binary_sensor(
            coordinator=coordinator,
            vm_id=container_id,
            key="status",
            name="Status",
            config_entry=config_entry,
            info_device=device_info(
                hass=hass,
                config_entry=config_entry,
                proxmox_type=ProxmoxType.LXC,
                vm_id=container_id,
            ),
        )
        sensors.append(container_sensor)

    async_add_entities(sensors)


def create_binary_sensor(
    coordinator,
    vm_id,
    key,
    name,
    config_entry,
    info_device,
):
    """Create a binary sensor based on the given data."""
    return ProxmoxBinarySensor(
        coordinator=coordinator,
        unique_id=f"proxmox_{config_entry.data[CONF_HOST]}_{config_entry.data[CONF_PORT]}_{config_entry.data[CONF_NODE]}_{vm_id}_{key}",
        name=name,
        icon="",
        device_class=BinarySensorDeviceClass.RUNNING,
        vm_id=vm_id,
        info_device=info_device,
    )


class ProxmoxBinarySensor(ProxmoxEntity, BinarySensorEntity):
    """A binary sensor for reading Proxmox VE data."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        unique_id,
        name,
        icon,
        device_class,
        vm_id,
        info_device,
    ):
        """Create the binary sensor for vms or containers."""
        super().__init__(coordinator, unique_id, name, icon, vm_id)

        self._attr_device_class = device_class
        self._attr_device_info = info_device

    @property
    def is_on(self):
        """Return the state of the binary sensor."""
        if (data := self.coordinator.data) is None:
            return None

        return data["status"] == "running"

    @property
    def available(self):
        """Return sensor availability."""

        return super().available and self.coordinator.data is not None
