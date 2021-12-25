"""Switch to set Proxmox VE data."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_HOST
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import ProxmoxClient, ProxmoxEntity, call_api_post_status, compile_device_info
from .const import (
    COMMAND_SHUTDOWN,
    COMMAND_START,
    CONF_CONTAINERS,
    CONF_NODE,
    CONF_NODES,
    CONF_VMS,
    COORDINATORS,
    DOMAIN,
    PROXMOX_CLIENTS,
    PROXMOX_SWITCH_TYPES,
    Node_Type,
)
from .model import ProxmoxSwitchDescription


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up switch."""
    if discovery_info is None:
        return

    switches = []

    for host_config in discovery_info["config"][DOMAIN]:
        host_name = host_config[CONF_HOST]
        host_name_coordinators = hass.data[DOMAIN][COORDINATORS][host_name]

        if hass.data[PROXMOX_CLIENTS][host_name] is None:
            continue

        proxmox_client = hass.data[PROXMOX_CLIENTS][host_name]

        for node_config in host_config[CONF_NODES]:
            node_name = node_config[CONF_NODE]

            for vm_id in node_config[CONF_VMS]:
                coordinator = host_name_coordinators[node_name][vm_id]

                # unfound vm case
                if (coordinator_data := coordinator.data) is None:
                    continue

                vm_name = coordinator_data["name"]
                device_info = compile_device_info(host_name, node_name, vm_id, vm_name)

                for description in PROXMOX_SWITCH_TYPES:
                    switches.append(
                        create_switch(
                            coordinator=coordinator,
                            device_info=device_info,
                            description=description,
                            node_name=node_name,
                            mid=vm_id,
                            name=vm_name,
                            proxmox_client=proxmox_client,
                            machine_type=Node_Type.TYPE_VM,
                        )
                    )

            for ct_id in node_config[CONF_CONTAINERS]:
                coordinator = host_name_coordinators[node_name][ct_id]

                # unfound container case
                if (coordinator_data := coordinator.data) is None:
                    continue

                ct_name = coordinator_data["name"]
                device_info = compile_device_info(host_name, node_name, ct_id, ct_name)
                for description in PROXMOX_SWITCH_TYPES:
                    switches.append(
                        create_switch(
                            coordinator=coordinator,
                            device_info=device_info,
                            description=description,
                            node_name=node_name,
                            mid=ct_id,
                            name=ct_name,
                            proxmox_client=proxmox_client,
                            machine_type=Node_Type.TYPE_CONTAINER,
                        )
                    )

    add_entities(switches)


def create_switch(
    coordinator: DataUpdateCoordinator,
    device_info: DeviceInfo,
    description: ProxmoxSwitchDescription,
    node_name: str,
    mid: str,
    name: str,
    proxmox_client: ProxmoxClient,
    machine_type: Node_Type,
):
    """Create a switch based on the given data."""
    return ProxmoxBinarySwitch(
        coordinator=coordinator,
        device_info=device_info,
        description=description,
        unique_id=f"proxmox_{node_name}_{mid}_{description.key}",
        name=f"{node_name}_{name}_{description.key}",
        proxmox_client=proxmox_client,
        node_name=node_name,
        vm_id=mid,
        machine_type=machine_type,
    )


class ProxmoxBinarySwitch(ProxmoxEntity, SwitchEntity):
    """A switch for reading/writing Proxmox VE status."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: DeviceInfo,
        description: ProxmoxSwitchDescription,
        name: str,
        unique_id: str,
        proxmox_client: ProxmoxClient,
        node_name: str,
        vm_id: str,
        machine_type: Node_Type,
    ):
        """Create the switch for vms or containers."""
        super().__init__(
            coordinator=coordinator,
            device_info=device_info,
            name=name,
            unique_id=unique_id,
        )
        self.entity_description = description

        def _turn_on_funct():
            """Post start command & tell HA state is on."""
            result = call_api_post_status(
                proxmox_client.get_api_client(),
                node_name,
                vm_id,
                machine_type,
                description.start_command,
            )
            if result is not None and COMMAND_START in result:
                # received success acknoledgement from API, set state optimistically to on
                self._attr_is_on = True
                self.async_write_ha_state()
                # TODO - QOL improvement - depending on polling overlap, there is still a possibility for the switch
                # to bounce if the server isn't fully on before the next polling cycle. Ideally need
                # to skip the next polling cycle if there is one scheduled in the next ~10 seconds

        def _turn_off_funct():
            """Post shutdown command & tell HA state is off."""
            result = call_api_post_status(
                proxmox_client.get_api_client(),
                node_name,
                vm_id,
                machine_type,
                description.stop_command,
            )
            if result is not None and COMMAND_SHUTDOWN in result:
                # received success acknoledgement from API, set state optimistically to off
                self._attr_is_on = False
                self.async_write_ha_state()
                # TODO - QOL improvement - depending on polling overlap, there is still a possibility for the switch
                # to bounce if the server isn't fully off before the next polling cycle. Ideally need
                # to skip the next polling cycle if there is one scheduled in the next ~10 seconds

        self._turn_on_funct = _turn_on_funct
        self._turn_off_funct = _turn_off_funct

    @property
    def is_on(self):
        """Return the switch."""
        if (data := self.coordinator.data) is None:
            return None

        return data["status"] == "running"

    @property
    def available(self):
        """Return sensor availability."""
        return super().available and self.coordinator.data is not None

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self._turn_on_funct()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._turn_off_funct()
